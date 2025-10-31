"""
CSV Import Service for cryptocurrency portfolio data
Supports flexible column mapping with template presets
"""
import csv
import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from difflib import SequenceMatcher
from dateutil import parser as date_parser
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class CSVImportService:
    """Service for importing cryptocurrency portfolio data from CSV files"""
    
    def __init__(self, templates_dir: str = None):
        """
        Initialize CSV import service
        
        Args:
            templates_dir: Directory containing exchange template JSON files
        """
        if templates_dir is None:
            # Get absolute path to templates directory
            current_file = os.path.abspath(__file__)  # backend/app/services/csv_import_service.py
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))  # backend
            templates_dir = os.path.join(backend_dir, 'templates')
        
        self.templates_dir = templates_dir
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Load all exchange templates from templates directory"""
        templates = {}
        
        if not os.path.exists(self.templates_dir):
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return templates
        
        for filename in os.listdir(self.templates_dir):
            if filename.endswith('.json'):
                exchange = filename[:-5]  # Remove .json extension
                template_path = os.path.join(self.templates_dir, filename)
                
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template = json.load(f)
                        templates[exchange.lower()] = template
                        logger.info(f"Loaded template for {exchange}")
                except Exception as e:
                    logger.error(f"Failed to load template {filename}: {e}")
        
        return templates
    
    def detect_exchange_format(self, headers: List[str]) -> Optional[str]:
        """
        Fuzzy match CSV headers against exchange templates
        
        Args:
            headers: List of CSV column headers
            
        Returns:
            Exchange name if detected, None otherwise
        """
        best_match_exchange = None
        best_match_score = 0.0
        threshold = 0.6
        
        for exchange, template in self.templates.items():
            score = self._calculate_header_match_score(headers, template)
            
            if score > best_match_score and score >= threshold:
                best_match_score = score
                best_match_exchange = exchange
        
        return best_match_exchange
    
    def _calculate_header_match_score(self, headers: List[str], template: Dict) -> float:
        """
        Calculate how well headers match a template
        
        Args:
            headers: CSV column headers
            template: Exchange template
            
        Returns:
            Match score between 0 and 1
        """
        total_score = 0.0
        matches = 0
        
        column_mapping = template.get('column_mapping', {})
        header_lower = [h.lower() for h in headers]
        
        for field, candidates in column_mapping.items():
            for header in headers:
                header_lower = header.lower()
                for candidate in candidates:
                    similarity = SequenceMatcher(None, header_lower, candidate.lower()).ratio()
                    if similarity >= 0.6:
                        total_score += similarity
                        matches += 1
                        break
        
        # Average match score
        return total_score / max(matches, 1)
    
    def parse_csv_file(self, file_content: bytes, encoding: str = 'utf-8') -> List[Dict[str, Any]]:
        """
        Parse CSV file content into list of dictionaries
        
        Args:
            file_content: Raw file bytes
            encoding: File encoding (try utf-8, fallback to latin-1)
            
        Returns:
            List of row dictionaries
        """
        # Try to decode with specified encoding
        try:
            content_str = file_content.decode(encoding)
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decoding failed, trying latin-1")
            try:
                content_str = file_content.decode('latin-1')
            except Exception as e:
                logger.error(f"Failed to decode CSV file: {e}")
                raise ValueError("Unable to decode CSV file. Please ensure it's valid UTF-8 or Latin-1.")
        
        # Remove BOM if present
        if content_str.startswith('\ufeff'):
            content_str = content_str[1:]
        
        # Parse CSV
        try:
            reader = csv.DictReader(content_str.splitlines())
            rows = []
            
            for row_num, row in enumerate(reader, start=1):
                # Clean up row (strip whitespace from keys and values)
                cleaned_row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                rows.append(cleaned_row)
            
            logger.info(f"Parsed {len(rows)} rows from CSV")
            return rows
            
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            raise ValueError(f"Invalid CSV format: {str(e)}")
    
    def get_template(self, exchange: str) -> Optional[Dict]:
        """Get template for specific exchange"""
        return self.templates.get(exchange.lower())
    
    def normalize_transaction(self, row: Dict[str, Any], template: Dict, exchange: str) -> Optional[Dict[str, Any]]:
        """
        Normalize a CSV row to internal transaction schema
        
        Args:
            row: CSV row dictionary
            template: Exchange template
            exchange: Exchange name
            
        Returns:
            Normalized transaction dict or None if invalid
        """
        try:
            column_mapping = template.get('column_mapping', {})
            
            # Extract fields using fuzzy matching
            symbol = self._extract_field(row, column_mapping.get('symbol', []), required=True)
            if not symbol:
                return None
            
            transaction_type = self._extract_field(row, column_mapping.get('type', []), required=True)
            if not transaction_type:
                return None
            
            # Parse quantity
            qty_str = self._extract_field(row, column_mapping.get('quantity', []), required=True)
            if not qty_str:
                return None
            
            quantity = self._parse_number(qty_str)
            if quantity is None or quantity <= 0:
                logger.warning(f"Invalid quantity: {qty_str}")
                return None
            
            # Parse value field
            value_str = self._extract_field(row, column_mapping.get('value', []), required=False)
            value = 0.0
            currency = "USD"
            
            if value_str:
                value, currency = self._parse_value_with_currency(value_str, exchange)
            
            # Parse price
            price_str = self._extract_field(row, column_mapping.get('price', []), required=True)
            if not price_str:
                # Fallback: calculate from value / quantity
                if value > 0 and quantity > 0:
                    price = value / quantity
                else:
                    logger.warning(f"Unable to determine price for {symbol}")
                    return None
            else:
                # Parse price which may contain currency
                price_value, _ = self._parse_value_with_currency(price_str, exchange)
                price = price_value
                if price is None or price <= 0:
                    logger.warning(f"Invalid price: {price_str}")
                    return None
            
            # Parse fees (optional)
            fees_str = self._extract_field(row, column_mapping.get('fees', []), required=False)
            fees = 0.0
            if fees_str:
                fees_value, _ = self._parse_value_with_currency(fees_str, exchange)
                fees = fees_value
            
            # Parse date (optional)
            date_str = self._extract_field(row, column_mapping.get('date', []), required=False)
            date = datetime.now().strftime("%Y-%m-%d")
            
            if date_str:
                try:
                    dt = date_parser.parse(date_str)
                    date = dt.strftime("%Y-%m-%d")  # Store only date
                except Exception as e:
                    logger.warning(f"Failed to parse date '{date_str}': {e}")
            
            return {
                'symbol': symbol.upper(),
                'type': transaction_type.lower(),
                'quantity': quantity,
                'price': price,
                'value': value,
                'fees': fees,
                'date': date,
                'currency': currency
            }
            
        except Exception as e:
            logger.error(f"Error normalizing transaction: {e}")
            return None
    
    def _extract_field(self, row: Dict, candidates: List[str], required: bool = False) -> Optional[str]:
        """Extract field from row using fuzzy matching"""
        if not candidates:
            return None
        
        for candidate in candidates:
            # Exact match
            if candidate in row and row[candidate]:
                return row[candidate]
            
            # Fuzzy match
            for key in row.keys():
                similarity = SequenceMatcher(None, key.lower(), candidate.lower()).ratio()
                if similarity >= 0.6:
                    return row[key]
        
        if required:
            logger.warning(f"Required field not found: {candidates}")
        
        return None
    
    def _parse_number(self, value_str: str) -> Optional[float]:
        """Parse number from string, handling commas and currency symbols"""
        if not value_str:
            return None
        
        # Remove common formatting
        value_str = value_str.replace(',', '').replace(' ', '').strip()
        
        # Try to extract numeric part (handle "2000.00 CZK" format)
        parts = value_str.split()
        if parts:
            try:
                return float(parts[0])
            except ValueError:
                pass
        
        return None
    
    def _parse_value_with_currency(self, value_str: str, exchange: str) -> Tuple[float, str]:
        """
        Parse value string to extract amount and currency
        
        Args:
            value_str: Value string like "2,000.00 CZK"
            exchange: Exchange name
            
        Returns:
            Tuple of (amount, currency)
        """
        # Remove commas
        value_str = value_str.replace(',', '').strip()
        
        # Split by space to separate amount and currency
        parts = value_str.split()
        
        if len(parts) >= 2:
            try:
                amount = float(parts[0])
                currency = parts[-1]  # Last part is usually currency
                
                # Map currency using template
                if exchange in self.templates:
                    currency_mapping = self.templates[exchange].get('currency_mapping', {})
                    for currency_code, patterns in currency_mapping.get('patterns', {}).items():
                        if currency in patterns:
                            currency = currency_code
                            break
                
                return amount, currency
            except ValueError:
                pass
        
        # Fallback: try to parse just the number
        try:
            amount = float(parts[0])
            return amount, "USD"
        except (ValueError, IndexError):
            return 0.0, "USD"
    
    def aggregate_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """
        Aggregate transactions by symbol with weighted average price
        
        Args:
            transactions: List of normalized transactions
            
        Returns:
            List of aggregated portfolio items
        """
        # Group by symbol
        by_symbol = {}
        for txn in transactions:
            symbol = txn['symbol']
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(txn)
        
        aggregated = []
        
        for symbol, txns in by_symbol.items():
            try:
                result = self._calculate_weighted_average(symbol, txns)
                if result:
                    aggregated.append(result)
            except Exception as e:
                logger.error(f"Error aggregating {symbol}: {e}")
        
        return aggregated
    
    def _calculate_weighted_average(self, symbol: str, transactions: List[Dict]) -> Optional[Dict]:
        """Calculate weighted average for a symbol's transactions"""
        buy_txns = [t for t in transactions if t['type'].lower() in ['buy', 'purchase']]
        sell_txns = [t for t in transactions if t['type'].lower() in ['sell', 'sale']]
        
        if not buy_txns:
            logger.warning(f"No buy transactions found for {symbol}")
            return None
        
        total_buy_qty = sum(t['quantity'] for t in buy_txns)
        total_sell_qty = sum(t['quantity'] for t in sell_txns)
        net_quantity = total_buy_qty - total_sell_qty
        
        if net_quantity <= 0:
            logger.info(f"Fully sold position for {symbol}, skipping")
            return None
        
        # Calculate weighted average price from buy transactions
        weighted_price = sum(t['quantity'] * t['price'] for t in buy_txns) / total_buy_qty
        # Only count fees and values from BUY transactions (sells don't contribute to investment)
        total_buy_fees = sum(t.get('fees', 0) for t in buy_txns)
        total_buy_value = sum(t.get('value', 0) for t in buy_txns)
        
        # Calculate total buy investment
        total_buy_investment = total_buy_value + total_buy_fees
        
        # For positions with partial sells, calculate remaining investment proportionally
        if total_sell_qty > 0:
            # Investment per coin = total buy investment / total buy quantity
            investment_per_coin = total_buy_investment / total_buy_qty if total_buy_qty > 0 else 0
            # Remaining investment = investment per coin * remaining quantity
            remaining_investment = investment_per_coin * net_quantity
            # Proportionally split remaining investment between value and fees
            value_ratio = total_buy_value / total_buy_investment if total_buy_investment > 0 else 0
            fees_ratio = total_buy_fees / total_buy_investment if total_buy_investment > 0 else 0
            total_value = remaining_investment * value_ratio
            total_fees = remaining_investment * fees_ratio
        else:
            total_value = total_buy_value
            total_fees = total_buy_fees
        
        # Get earliest buy date
        earliest_date = min(t['date'] for t in buy_txns)
        
        # Get currency from first transaction
        currency = transactions[0].get('currency', 'USD')
        
        return {
            'symbol': symbol,
            'quantity': net_quantity,
            'price': weighted_price,
            'value': total_value,
            'fees': total_fees,
            'date': earliest_date,
            'currency': currency,
            'transactions_count': len(transactions)
        }

