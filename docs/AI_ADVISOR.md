# AI Advisor Documentation

## Overview

The AI Advisor feature provides intelligent price predictions for cryptocurrencies using OpenRouter AI models, combined with news sentiment analysis and historical price trends. Predictions are automatically generated for all portfolio symbols and alert symbols, with historical performance tracking to improve accuracy over time.

## Features

### 1. AI Price Predictions

- **Timeframes**: 24 hours, 1 week, 1 month, 1 year
- **Confidence Scores**: Each prediction includes a percentage confidence based on:
  - Data quality and availability
  - News sentiment consistency
  - Market volatility
  - Historical accuracy
- **Model Tracking**: Predictions are tagged with the AI model used, enabling performance comparison

### 2. News Analysis

- **Automatic News Fetching**: Fetches recent cryptocurrency news from NewsAPI
- **Sentiment Analysis**: Calculates sentiment scores (-1 to 1) for each article
- **Relevance Scoring**: Determines how relevant each article is to the specific cryptocurrency
- **News Summary**: Provides summarized news context for AI predictions

### 3. Price Charts

- **Mini Charts**: 7-day price trends displayed on portfolio items
- **Full Charts**: 1-year detailed charts on symbol detail pages
- **Interactive**: Click mini charts to navigate to detailed symbol pages
- **Real-time Updates**: Charts update automatically with current price data

### 4. Performance Tracking

- **Prediction Verification**: Automatic verification of past predictions against actual prices
- **Accuracy Metrics**: Tracks accuracy percentage for each prediction
- **Model Comparison**: Compare performance across different AI models
- **Historical Stats**: View aggregated performance statistics per symbol and model

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=your-openrouter-api-key-here
OPENROUTER_MODEL=openai/gpt-4  # or google/gemini-2.0-flash-exp:free, anthropic/claude-3-opus, etc.

# News API Configuration
NEWS_API_KEY=your-news-api-key-here

# Prediction Update Interval
AI_PREDICTION_INTERVAL_HOURS=24  # How often to regenerate predictions
```

### Getting API Keys

1. **OpenRouter API Key**:
   - Sign up at [OpenRouter.ai](https://openrouter.ai)
   - Navigate to Keys section
   - Create a new API key
   - Copy and add to `.env` as `OPENROUTER_API_KEY`

2. **NewsAPI Key**:
   - Sign up at [NewsAPI.org](https://newsapi.org)
   - Get your free API key from the dashboard
   - Copy and add to `.env` as `NEWS_API_KEY`

3. **Model Selection**:
   - Default: `openai/gpt-4`
   - Free option: `google/gemini-2.0-flash-exp:free`
   - Premium options: `anthropic/claude-3-opus`, `openai/gpt-4-turbo`, etc.
   - See [OpenRouter Models](https://openrouter.ai/models) for full list

## How It Works

### Prediction Generation Flow

1. **Data Collection**:
   - Current price from multi-exchange price service
   - 30-day price trend data
   - Recent news articles (last 7 days)
   - News sentiment scores

2. **AI Analysis**:
   - OpenRouter API is called with comprehensive context
   - AI model analyzes all data points
   - Generates predictions for all timeframes
   - Provides reasoning for each prediction

3. **Storage**:
   - Predictions stored in `ai_predictions` table
   - Model name saved for performance tracking
   - Confidence scores and reasoning stored

4. **Verification**:
   - Background task checks past predictions
   - Compares predicted prices with actual prices
   - Calculates accuracy percentages
   - Updates performance statistics

### Background Tasks

1. **Prediction Updater** (`background_ai_advisor_updater`):
   - Runs every `AI_PREDICTION_INTERVAL_HOURS` (default: 24)
   - Generates predictions for all portfolio and alert symbols
   - Only regenerates if predictions are older than the interval

2. **Prediction Verifier** (`background_prediction_verifier`):
   - Runs every 6 hours
   - Checks predictions that have reached their target timeframe
   - Verifies accuracy and updates statistics

## API Endpoints

### Predictions

- `GET /api/ai-advisor/predictions/{symbol}` - Get predictions for a symbol
- `GET /api/ai-advisor/predictions/portfolio` - Get predictions for all portfolio symbols
- `POST /api/ai-advisor/generate/{symbol}` - Manually trigger prediction generation

### Performance

- `GET /api/ai-advisor/performance/{symbol}` - Get performance stats for a symbol
- `GET /api/ai-advisor/performance/by-model` - Get performance stats grouped by model

### News

- `GET /api/ai-advisor/news/{symbol}?days=7` - Get recent news analysis for a symbol

### Charts

- `GET /api/charts/history/{symbol}?days=365` - Get 1-year price history
- `GET /api/charts/mini/{symbol}?days=7` - Get 7-day mini chart data

## Frontend Usage

### Portfolio View

Predictions and charts are automatically displayed on each portfolio item in card view:

- Mini 7-day price chart (clickable for detailed view)
- AI predictions card with all timeframes
- Confidence scores and reasoning

### Symbol Detail Page

Navigate to `/symbol/{SYMBOL}` for comprehensive analysis:

- Full 1-year price chart
- Complete AI predictions display
- Recent news with sentiment analysis
- Historical prediction performance
- Model comparison statistics

### Manual Prediction Generation

Users can manually trigger prediction generation:

- Click "Regenerate Predictions" button on symbol detail page
- Or use the "Generate Predictions" button in AI Advisor card when no predictions exist

## Database Schema

### ai_predictions Table

```sql
CREATE TABLE ai_predictions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    symbol TEXT NOT NULL,
    prediction_type TEXT NOT NULL,  -- '24h', 'week', 'month', 'year'
    predicted_price REAL NOT NULL,
    confidence_percent REAL NOT NULL,
    prediction_reasoning TEXT,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    actual_price_at_target REAL,
    is_verified BOOLEAN DEFAULT FALSE,
    accuracy_percent REAL
);
```

### news_analysis Table

```sql
CREATE TABLE news_analysis (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    news_date TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    sentiment_score REAL,
    relevance_score REAL,
    source TEXT,
    created_at TIMESTAMP NOT NULL
);
```

### price_history_cache Table

```sql
CREATE TABLE price_history_cache (
    symbol TEXT PRIMARY KEY,
    history_data TEXT NOT NULL,  -- JSON array of price points
    last_updated TIMESTAMP NOT NULL
);
```

## Best Practices

1. **API Rate Limits**:
   - OpenRouter and NewsAPI have rate limits
   - Predictions are cached and only regenerated when needed
   - News is cached for 1 hour

2. **Model Selection**:
   - Start with free models for testing
   - Monitor performance to find best model for your use case
   - Different models may perform better for different cryptocurrencies

3. **Cost Management**:
   - Free models: `google/gemini-2.0-flash-exp:free`
   - Paid models provide better accuracy but cost more
   - Adjust `AI_PREDICTION_INTERVAL_HOURS` to control API usage

4. **Performance Monitoring**:
   - Check performance stats regularly
   - Compare model accuracy
   - Adjust model selection based on performance data

## Troubleshooting

### Predictions Not Appearing

- Check that `OPENROUTER_API_KEY` is set correctly
- Verify API key has sufficient credits/access
- Check backend logs for error messages
- Ensure symbols are valid (e.g., "BTC" not "bitcoin")

### News Not Loading

- Verify `NEWS_API_KEY` is set correctly
- Check NewsAPI rate limits (free tier: 100 requests/day)
- News fetching gracefully degrades if unavailable

### Charts Not Displaying

- Historical price data requires CoinGecko API (no key needed, but rate limited)
- Charts will show "No data" if symbol not found on CoinGecko
- Check browser console for errors

### Low Prediction Accuracy

- Review news sentiment scores
- Check if market conditions are unusually volatile
- Consider trying different AI models
- Review prediction reasoning to understand AI's logic

## Future Enhancements

- Multiple model predictions per symbol (ensemble)
- Custom prediction timeframes
- User preference for model selection
- Email/SMS notifications for significant prediction changes
- Integration with trading strategies
- Technical indicator analysis
- Social media sentiment analysis
