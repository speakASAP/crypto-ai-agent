# Binance Import Quick Reference

> 📚 **Full Documentation**: [Binance Import Guide](BINANCE_IMPORT_GUIDE.md)

## 🚀 Quick Start

### 1. Get Binance API Key

- Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)
- Create API key with **"Enable Reading"** permission
- Copy API Key and Secret Key

### 2. Update Environment

```bash
# Add to .env file
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_key_here
```

### 3. Import Portfolio

```bash
# Test import
python test_binance_import.py
```

## 📋 API Endpoints

| Endpoint | Method | Purpose |
| -------- | ------ | ------- |
| `/api/import/binance/test-connection` | POST | Test API credentials |
| `/api/import/binance/preview` | POST | Preview import without saving |
| `/api/import/binance/execute` | POST | Execute import and save |
| `/api/import/history` | GET | View import history |

## 🔧 Troubleshooting

### Common Issues

| Error | Cause | Solution |
| ----- | ----- | -------- |
| `Signature for this request is not valid` | Wrong API secret | Regenerate API key |
| `Invalid API-key, IP, or permissions` | No reading permission | Enable "Enable Reading" |
| `Binance API is not accessible: 404` | Wrong API URL | Check `BINANCE_API_URL` |
| `No balances found` | Empty account | Ensure Binance has holdings |

### Debug Commands

```bash
# Test API credentials
python test_binance_direct.py

# Test import service
python test_binance_service.py

# Check configuration
cd backend && python -c "
from app.core.config import settings
print(f'API Key: {settings.binance_api_key[:10]}...')
"
```

## 📊 What Gets Imported

- ✅ All cryptocurrency holdings from Binance
- ✅ Real-time price tracking
- ✅ Multi-currency support (USD, EUR, CZK)
- ✅ Source tracking ("Binance")
- ✅ Import history

## 🔒 Security

- **Read-only access** - Cannot trade or withdraw
- **User isolation** - Only you see your data
- **Secure encryption** - Industry-standard HMAC
- **Duplicate prevention** - Won't import duplicates

## 📈 Performance

- **API Rate Limits**: 1200 requests/minute (we use ~13 per import)
- **Import Speed**: ~2-3 seconds for typical portfolio
- **Database**: Optimized with indexes
- **Caching**: 30-minute exchange rate cache

---

**Need Help?** Check the [full documentation](BINANCE_IMPORT_GUIDE.md) or review backend logs.
