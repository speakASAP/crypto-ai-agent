# CSV Portfolio Import Guide

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [Technical Implementation](TECHNICAL_IMPLEMENTATION.md)

## Overview

The CSV Portfolio Import feature allows users to import cryptocurrency transaction history from any exchange that supports CSV export. The system uses flexible column mapping with automatic template detection to handle various CSV formats.

## Features

- ✅ **Flexible Column Mapping** - Automatically detect and map CSV columns
- ✅ **Template Presets** - Pre-configured templates for Revolut, Coinbase, and Binance
- ✅ **Fuzzy Header Matching** - Intelligent column detection with Levenshtein similarity
- ✅ **Transaction Aggregation** - Combine multiple buy/sell transactions into net positions
- ✅ **Weighted Average Pricing** - Calculate accurate buy prices from transaction history
- ✅ **Multi-Currency Support** - Automatic USD conversion for all currencies
- ✅ **Duplicate Prevention** - Avoid importing duplicate positions
- ✅ **Import History** - Track all CSV imports

## Supported Exchanges

### Revolut (✅ Fully Tested)

**CSV Format:**

- **Required Fields**: Symbol, Type, Quantity, Price, Value
- **Optional Fields**: Fees, Date
- **Date Format**: "Oct 21, 2025, 2:36:35 PM"
- **Currency**: Auto-detected from value field (e.g., "2,000.00 CZK")

**Sample CSV:**

```csv
Symbol,Type,Quantity,Price,Value,Fees,Date
ONDO,Buy,128.2149791,15.60 CZK,"2,000.00 CZK",45.00 CZK,"Oct 21, 2025, 2:36:35 PM"
ETH,Buy,0.02419027,"82,677.84 CZK","2,000.00 CZK",44.99 CZK,"Oct 21, 2025, 3:05:50 PM"
```

### Coinbase (Template Available)

**CSV Format:**

- **Required Fields**: Timestamp, Transaction Type, Asset, Quantity Transacted
- **Optional Fields**: Spot Price Currency, Subtotal, Fees and/or Spread

### Binance (Template Available)

**CSV Format:**

- **Required Fields**: User_ID, UTC_Time, Account, Operation
- **Optional Fields**: Coin, Change, Remark

## Usage

### Method 1: API Endpoints

#### Preview CSV Import (No Database Changes)

```bash
curl -X POST "http://localhost:8100/api/import/csv/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@your_transactions.csv"
```

**Response:**

```json
{
  "success": true,
  "message": "Successfully parsed CSV file. Found 15 unique symbols from 19 transactions.",
  "detected_exchange": "revolut",
  "preview_data": [...],
  "total_rows": 19,
  "aggregated_items": [
    {
      "symbol": "ONDO",
      "quantity": 128.2149791,
      "price": 15.6,
      "fees": 45.0,
      "date": "2025-10-21",
      "currency": "CZK"
    }
  ],
  "errors": []
}
```

#### Execute CSV Import (Save to Database)

```bash
curl -X POST "http://localhost:8100/api/import/csv/execute" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@your_transactions.csv" \
  -d '{"exchange": "revolut"}'
```

**Response:**

```json
{
  "success": true,
  "message": "Successfully imported 15 portfolio items from CSV",
  "items_imported": 15,
  "total_found": 15
}
```

#### Get Available Templates

```bash
curl -X GET "http://localhost标准:8100/api/import/csv/templates" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### View Import History

```bash
curl offers GET "http://localhost:8100/api/import/history" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Method 2: Web Interface (Coming Soon)

1. Navigate to Portfolio settings
2. Click "Import from CSV"
3. Upload your CSV file
4. Review preview of aggregated positions
5. Click "Confirm Import"

## How It Works

### 1. Template Detection

The system automatically detects the exchange format by:

1. Extracting CSV headers
2. Fuzzy matching against known templates using Levenshtein distance
3. Calculating match scores for each template
4. Selecting the best match (threshold: 60% similarity)

### 2. Transaction Normalization

Each CSV row is normalized to an internal schema:

```python
{
    "symbol": "ONDO",
    "type": "buy",  # or "sell"
    "quantity": 128.2149791,
    "price": 15.6,
    "value": 2000.0,
    "fees": 45.0,
    "date": "2025-10-21",
    "currency": "CZK"
}
```

### 3. Transaction Aggregation

Multiple transactions for the same symbol are aggregated:

**Example:**

```text
XRP Buy 9.639722 @ 51.87 CZK
XRP Buy 29.09079 @ 51.56 CZK
```

↓

```text
XRP: 38.730512 (net quantity) @ 51.637 (weighted average price)
```

**Aggregation Logic:**

- Net quantity = sum(buys) - sum(sells)
- Weighted avg price = sum(buy_qty * buy_price) / sum(buy_qty)
- Total fees = sum(all fees)
- Earliest purchase date = min(buy dates)

### 4. Currency Conversion

All values are automatically converted to USD:

- Prices and fees converted using current exchange rates
- Original currency stored in `base_currency` field
- Exchange rate at purchase recorded for historical accuracy

### 5. Duplicate Prevention

Imports skip positions that already exist:

- Same symbol
- Same quantity (±0.001 tolerance)

## Technical Implementation

### Database Schema

#### CSV Import Mappings Table

```sql
CREATE TABLE csv_import_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exchange TEXT NOT NULL,
    column_mapping TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id),
    UNIQUE(user_id, exchange)
)
```

### Service Architecture

#### CSVImportService

- **File**: `backend/app/services/csv_import_service.py`
- **Purpose**: Handle CSV parsing, template matching, and transaction aggregation
- **Key Methods**:
  - `detect_exchange_format()` - Fuzzy match headers against templates
  - `parse_csv_file()` - Parse CSV into dictionaries
  - `normalize_transaction()` - Normalize to internal schema
  - `aggregate_transactions()` - Combine buy/sell transactions
  - `_calculate_weighted_average()` - Calculate weighted price

### API Endpoints

- **File**: `backend/app/main.py`
- **Endpoints**:
  - `POST /api/import/csv/upload` - Preview CSV without saving
  - `POST /api/import/csv/execute` - Execute import and save to database
  - `GET /api/import/csv/templates` - Get available templates
  - `GET /api/import/csv/mapping/{exchange}` - Get saved mapping
  - `POST /api/import/csv/mapping/{exchange}` - Save custom mapping

## Error Handling

### Common Issues

#### 1. "Could not detect exchange format"

- **Cause**: CSV headers don't match any known template
- **Solution**:
  - Check CSV format matches a supported exchange
  - Use template files in `backend/templates/` as reference
  - Consider manual column mapping (coming soon)

#### 2. "Invalid CSV format"

- **Cause**: File is not a valid CSV file
- **Solution**: Ensure file has .csv extension and proper formatting

#### 3. "File size exceeds 10MB"

- **Cause**: CSV file too large
- **Solution**: Split into smaller files or remove unnecessary data

#### 4. "No valid transactions found"

- **Cause**: All rows failed to parse
- **Solution**: Check date formats, number formats, and currency symbols

### Validation Rules

- **Required Fields**: Symbol, Type, Quantity, Price, Value
- **Price**: Must be > 0
- **Quantity**: Must be > 0
- **Date**: Stored as YYYY-MM-DD only
- **File Size**: Max 10MB
- **Encoding**: UTF-8 or Latin-1

## Performance Considerations

### File Size Limits

- **Max File Size**: 10MB
- **Typical Performance**:
  - Small files (<100 transactions): <1 second
  - Medium files (100-1000): 1-3 seconds
  - Large files (1000+): 3-10 seconds

### Aggregation Performance

- O(n) complexity for aggregation
- Caching of exchange rates (30-minute duration)
- Batch database inserts for efficiency

## Creating Custom Templates

Templates are JSON files in `backend/templates/`:

```json
{
  "exchange": "custom_exchange",
  "name": "Custom Exchange",
  "required_fields": ["Symbol", "Type", "Quantity"],
  "optional_fields": ["Date", "Fees"],
  "column_mapping": {
    "symbol": ["Symbol", "Coin", "Asset"],
    "type": ["Type", "Transaction Type"],
    "quantity": ["Quantity", "Amount"],
    "price": ["Price", "Rate"],
    "value": ["Value", "Total"],
    "fees": ["Fees", "Fee"],
    "date": ["Date", "Timestamp"]
  },
  "date_formats": ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"],
  "currency_mapping": {
    "default": "USD",
    "patterns": {
      "USD": ["USD", "$"],
      "EUR": ["EUR", "€"]
    }
  }
}
```

## Future Enhancements

### Planned Features

1. **Manual Column Mapping UI** - Drag-and-drop column mapper
2. **Multi-File Import** - Import from multiple CSVs at once
3. **Partial Imports** - Import only selected symbols
4. **Custom Templates** - User-created template library
5. **Import Scheduling** - Automatic re-imports

### Additional Exchange Support

- Kraken
- Gemini
- KuCoin
- Crypto.com
- Bybit

## Troubleshooting

### Debug Commands

#### Test CSV Service

```bash
cd backend
python -c "
from app.services.csv_import_service import CSVImportService
service = CSVImportService()
print(f'Templates: {list(service.templates.keys())}')
"
```

#### Check Import History

```bash
curl -X GET "http://localhost:8100/api/import/history" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Log Analysis

Check backend logs for detailed import information:

```bash
tail -f logs/backend.log | grep "CSV import"
```

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review backend logs
3. Verify CSV format matches template
4. Test with a small CSV file first

---

**Last Updated**: 2025-01-28  
**Version**: 1.0.0  
**Status**: Production Ready

## Related Documentation

- [Main README](README.md) - Complete project overview
- [Binance Import Guide](BINANCE_IMPORT_GUIDE.md) - Binance API import
- [Bitfinex Import Guide](BITFINEX_IMPORT_GUIDE.md) - Bitfinex API import
- [Technical Implementation](TECHNICAL_IMPLEMENTATION.md) - Technical details
