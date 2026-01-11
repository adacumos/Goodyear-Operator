# Goodyear RAG Agent - Analytics & Forecasting Guide

## 🎯 Overview

Goodyear RAG Agent **intelligent analytical capabilities** that enable it to:
- 📊 Analyze sales trends and patterns
- 🔮 Forecast future orders, revenue, and shipments
- 📈 Calculate key manufacturing metrics
- 💡 Provide actionable business recommendations
- 🎓 Think like a manufacturing analyst

---

## 📦 New Files Added

### 1. `analytics_helper.py` ⭐ NEW
**Purpose:** Provides analytical and forecasting functions

**Key Features:**
- Trend analysis (moving averages, growth rates)
- Simple linear forecasting
- Data extraction from search results
- Automated insight generation

### 2. `instructions.txt` 🔄 ENHANCED
**Purpose:** Teaches AI to think analytically

**New Sections:**
- Analytical Capabilities & Forecasting
- Trend Analysis Guidelines
- Forecasting Methods (3 approaches)
- Confidence Level Definitions
- Key Metrics Calculations
- Example Analytical Interactions

### 3. `app.py` 🔄 ENHANCED
**Purpose:** Integrates analytics into conversation flow

**New Features:**
- Automatic analytical query detection
- Analytics context generation
- Enhanced validation for analytical responses
- Higher token limit (4000) for detailed analysis

### 4. `test_analytics.py` ⭐ NEW
**Purpose:** Validates analytical capabilities

**Tests:**
- Numeric extraction
- Moving averages
- Growth rate calculations
- Forecasting algorithms
- Search result analysis

---

## 🚀 Quick Start

### Step 1: Add New Files
```bash
# Copy the new files to your project
cp analytics_helper.py /path/to/your/project/
cp test_analytics.py /path/to/your/project/

# Replace existing files
cp app.py /path/to/your/project/app.py  # Enhanced version
cp instructions.txt /path/to/your/project/instructions.txt  # Enhanced version
```

### Step 2: Test Analytics Features
```bash
python test_analytics.py
```

**Expected Output:**
```
✅ PASS - Numeric Extraction
✅ PASS - Moving Average
✅ PASS - Growth Rate
✅ PASS - Linear Forecast
✅ PASS - Search Analysis
✅ PASS - Forecast Insights
✅ PASS - Context Creation
✅ PASS - Edge Cases

Tests Passed: 8/8
🎉 All analytics tests passed!
```

### Step 3: Deploy
```bash
# Deploy updated files to Azure
az webapp up --name goodyear-rag-agent --resource-group <your-rg>
```

---

## 📊 Analytical Capabilities

### 1. Trend Analysis
**What it does:** Identifies patterns in historical data

**Example Queries:**
- "What are my sales trends?"
- "Show me order patterns over the last quarter"
- "Is my revenue increasing or decreasing?"

**AI Response Includes:**
- Period-over-period growth rates
- Moving averages
- Pattern identification (seasonal, cyclical)
- Visual data in tables

**Sample Response:**
```
Sales Trend Analysis (Q4 2025):

| Month | Orders | Revenue | Growth |
|-------|--------|---------|--------|
| Oct   | 142    | $265K   | --     |
| Nov   | 158    | $289K   | +9.0%  |
| Dec   | 171    | $312K   | +8.2%  |

Key Finding: Consistent upward trend (+8.5% avg growth)
Confidence: HIGH (3 months consistent data)
```

---

### 2. Forecasting (3 Methods)

#### Method A: Simple Moving Average
**Best for:** Short-term (1-3 months), stable demand

**How it works:** Averages last N periods

**Example:**
```
User: "Forecast next month's orders"

AI: "Based on 3-month moving average:
- Nov: 158 orders
- Dec: 171 orders  
- Jan: 185 orders
- Average: 171 orders

Forecast February: 170-175 orders
Confidence: MEDIUM"
```

#### Method B: Trend Projection
**Best for:** Medium-term (3-6 months), trending data

**How it works:** Calculates growth rate and projects forward

**Example:**
```
User: "Predict Q1 revenue"

AI: "Historical growth analysis:
- Average monthly growth: +8.2%
- Last month revenue: $312K

Q1 Forecast:
- January: $337K (+8.2%)
- February: $365K (+8.2%)
- March: $395K (+8.2%)
Total Q1: ~$1.1M

Confidence: MEDIUM (assumes growth continues)"
```

#### Method C: Pattern Recognition
**Best for:** Long-term (6-12 months), seasonal data

**How it works:** Identifies recurring patterns (seasonality)

**Example:**
```
User: "What should I expect for Q3?"

AI: "Seasonal pattern detected:
- Q1 average: 150 orders (baseline)
- Q2 average: 185 orders (+23%)
- Q3 average: 210 orders (+40%)
- Q4 average: 165 orders (+10%)

Q3 2026 Forecast: 205-215 orders
Reason: Historical Q3 peak (+40% vs Q1)
Confidence: HIGH (3 years historical pattern)"
```

---

### 3. Key Metrics Calculated

The system automatically calculates:

**Volume Metrics:**
- Total units (shipped/ordered)
- Average order size
- Order frequency
- Backorder quantities

**Revenue Metrics:**
- Total revenue
- Average order value
- Revenue per customer
- Price trends

**Operational Metrics:**
- Fulfillment rate (%)
- Average lead time (days)
- On-time delivery (%)
- Backorder rate (%)

**Customer Metrics:**
- Active customer count
- Customer concentration (%)
- Repeat vs. new customers
- Order frequency by customer

---

### 4. Business Intelligence Queries

#### Customer Prioritization
**Query:** "Which customers should I focus on?"

**AI Analysis:**
- Revenue contribution by customer
- Growth trends per customer
- Order frequency patterns
- At-risk customer identification

**Output:**
```
Customer Prioritization:

Tier 1 - Strategic Accounts (70% revenue):
- ACME: $198K, +12%, MAINTAIN
- Baldwin: $145K, +8%, GROW
- Century: $112K, -3%, PROTECT ⚠️

Action Items:
1. Schedule call with Century (declining)
2. Expand offering to Baldwin (growing)
3. QBR with ACME (stable)
```

#### Capacity Planning
**Query:** "Can we handle expected demand?"

**AI Analysis:**
- Current backlog
- Forecasted new orders
- Historical fulfillment capacity
- Bottleneck identification

#### Product Analysis
**Query:** "Which products are trending?"

**AI Analysis:**
- Volume by product line
- Growth rates by SKU
- Seasonal product patterns
- Inventory recommendations

---

## 🎓 How the AI Thinks (Behind the Scenes)

### Query Processing Flow

```
1. User Query: "Forecast next month's revenue"
   ↓
2. System detects: Analytical query (keyword: "forecast")
   ↓
3. Search executes: Retrieves historical shipment data
   ↓
4. Analytics Helper processes results:
   - Extracts revenue values: [$265K, $289K, $312K]
   - Calculates growth rate: +8.5% average
   - Generates forecast: $337K (next month)
   ↓
5. AI receives enhanced context:
   - Original search results
   - Analytical summary (auto-generated)
   - Key metrics summary
   ↓
6. AI generates response:
   - Uses forecasting guidelines from instructions
   - Presents data in tables
   - States confidence level
   - Provides recommendations
   ↓
7. Response validation:
   - Checks for numbers ✓
   - Checks for confidence level ✓
   - Checks for recommendations ✓
```

---

## 💡 Example Analytical Queries

### Beginner Queries
```
✅ "How many orders did I have last month?"
✅ "What's my total revenue this quarter?"
✅ "Who are my top 3 customers?"
✅ "Show me recent shipments"
```

### Intermediate Queries
```
✅ "What are my sales trends over the last 3 months?"
✅ "Compare this month's revenue to last month"
✅ "Which customers are growing fastest?"
✅ "What's my average order size?"
```

### Advanced Queries
```
✅ "Forecast next quarter's order volume with confidence levels"
✅ "Analyze customer concentration risk and recommend diversification"
✅ "Predict inventory requirements for next month based on trends"
✅ "What seasonal patterns exist in my order data?"
✅ "Should I increase production capacity? Why or why not?"
```

---

## 🔧 Customizing Analytics Behavior

### Adjust Forecasting Parameters

**In `analytics_helper.py`:**

```python
# Change moving average window
def calculate_moving_average(values: List[float], window: int = 3):
    # Change window=3 to window=6 for longer-term smoothing
```

```python
# Adjust confidence thresholds
def simple_linear_forecast(...):
    # Current: std_dev < 0.1 = "high"
    # Change to: std_dev < 0.05 for stricter "high" confidence
```

### Adjust AI Temperature for Analytics

**In `app.py`:**

```python
# Current: temperature=0.3 (balanced)
model = create_model_from_config(
    temperature=0.2,  # Lower = more conservative forecasts
    # OR
    temperature=0.4,  # Higher = more creative insights
    max_tokens=4000
)
```

**Guidelines:**
- **0.1-0.2:** Very conservative, factual forecasts
- **0.3-0.4:** Balanced analytical reasoning (recommended)
- **0.5-0.6:** More creative insights, risk of speculation

---

## 📈 Model Parameters Optimized for Analytics

### Current Configuration
```python
temperature=0.3        # Balanced for analysis
max_tokens=4000        # High for detailed responses
top_p=0.9             # Focused sampling
frequency_penalty=0.3  # Reduce repetition
presence_penalty=0.2   # Encourage diverse perspectives
```

### Why These Settings?

**Temperature (0.3):**
- Low enough for factual accuracy
- High enough for analytical reasoning
- Balances precision with insight

**Max Tokens (4000):**
- Supports detailed trend analysis
- Allows for multiple tables
- Enables comprehensive forecasts

**Presence Penalty (0.2):**
- Encourages discussing multiple aspects
- Helps AI consider different scenarios
- Promotes comprehensive analysis

---

## 🧪 Testing Analytical Features

### Run Full Test Suite
```bash
python test_analytics.py
```

### Manual Testing Checklist

**Test 1: Basic Trend Analysis**
```
Query: "What are my sales trends?"
Expected: 
- ✅ Shows period-over-period data
- ✅ Calculates growth rates
- ✅ Presents in table format
- ✅ Identifies pattern (up/down/stable)
```

**Test 2: Simple Forecast**
```
Query: "Forecast next month's orders"
Expected:
- ✅ States methodology (e.g., "3-month moving average")
- ✅ Shows historical baseline
- ✅ Provides specific forecast number
- ✅ States confidence level
```

**Test 3: Customer Analysis**
```
Query: "Which customers should I prioritize?"
Expected:
- ✅ Ranks customers by revenue
- ✅ Shows growth trends
- ✅ Identifies risks (declining customers)
- ✅ Provides action items
```

**Test 4: Insufficient Data**
```
Query: "Forecast revenue for next year"
Expected:
- ✅ Acknowledges limited data
- ✅ States LOW confidence or recommends waiting
- ✅ Doesn't make up numbers
- ✅ Suggests data collection approach
```

---

## 🚨 Common Issues & Solutions

### Issue 1: AI Not Providing Forecasts
**Symptom:** AI says "I can't forecast" even with data

**Solutions:**
1. Check if `analytics_helper.py` is in project root
2. Verify `from analytics_helper import...` in `app.py`
3. Run `test_analytics.py` to validate functions work
4. Check logs for import errors

### Issue 2: Forecasts Are Inaccurate
**Symptom:** Predictions don't match reality

**Solutions:**
1. Verify sufficient historical data (3+ periods)
2. Check for data quality issues (outliers)
3. Lower confidence level in instructions
4. Add caveats about assumptions

### Issue 3: Analytics Context Not Generated
**Symptom:** Missing "Analytical Summary" in logs

**Solutions:**
```python
# Add debug logging in app.py
if is_analytical:
    logger.debug(f"Raw search output: {data_context.output[:200]}")
    analytics_context = create_analytics_context(data_context.output)
    logger.debug(f"Analytics context: {analytics_context[:200]}")
```

### Issue 4: AI Responses Too Long
**Symptom:** Responses truncated or incomplete

**Solutions:**
1. Increase `max_tokens` to 5000 in `app.py`
2. Or teach AI to be more concise in instructions
3. Consider pagination for very long analyses

---

## 📚 Advanced Use Cases

### 1. Multi-Period Forecasting
```
Query: "Forecast next 3 months of revenue with breakdown"

AI generates:
- Month-by-month forecast
- Cumulative totals
- Confidence intervals per period
- Scenario analysis (best/worst/likely)
```

### 2. Comparative Analysis
```
Query: "Compare Q4 2025 to Q4 2024"

AI provides:
- Year-over-year growth
- Same-period comparisons
- Seasonal adjustments
- Market context (if available)
```

### 3. What-If Scenarios
```
Query: "What if I lose Customer X? Impact on revenue?"

AI calculates:
- Customer X contribution
- Revenue impact (% and $)
- Mitigation strategies
- Recovery timeline
```

### 4. Inventory Optimization
```
Query: "How much inventory should I stock for next month?"

AI considers:
- Forecasted order volume
- Historical lead times
- Safety stock requirements
- Seasonal patterns
```

---

## 🎯 Success Metrics

Track these to measure analytics effectiveness:

**Accuracy Metrics:**
- Forecast accuracy (actual vs. predicted)
- Trend identification accuracy
- Customer prioritization effectiveness

**Usage Metrics:**
- % of queries that are analytical
- User satisfaction (thumbs up/down)
- Follow-up question rate

**Business Impact:**
- Decision speed (time to insight)
- Forecast utilization rate
- Revenue from prioritized customers

---

## 🔮 Future Enhancements (Roadmap)

### Phase 2: Advanced Analytics
- Machine learning forecasts (ARIMA, Prophet)
- Anomaly detection
- Real-time alerting
- Automated reports

### Phase 3: Predictive Insights
- Customer churn prediction
- Demand sensing
- Price optimization
- Capacity planning automation

### Phase 4: Prescriptive Analytics
- Automated recommendations
- Action prioritization
- ROI calculations
- A/B testing suggestions

---

## 📞 Getting Help

### Debugging Analytics Issues

1. **Check logs:**
```bash
# Look for analytics-related messages
grep "analytics" app.log
grep "forecast" app.log
```

2. **Validate analytics helper:**
```bash
python -c "from analytics_helper import ManufacturingAnalytics; print('✅ Import successful')"
```

3. **Test with sample data:**
```bash
python test_analytics.py
```

### Common Log Messages

**✅ Good:**
```
INFO - Detected analytical query: forecast...
INFO - Generated analytics context for analytical query
INFO - Retrieved 15 chunks from 15 results
```

**⚠️ Warning:**
```
WARNING - Analytical response missing: recommendations
WARNING - Insufficient data for forecast
```

**❌ Error:**
```
ERROR - Analytics context generation failed
ERROR - Import analytics_helper failed
```

---

## ✅ Deployment Checklist

Before deploying analytics features:

- [ ] `analytics_helper.py` added to project
- [ ] `instructions.txt` replaced with enhanced version
- [ ] `app.py` replaced with analytics-enabled version
- [ ] `test_analytics.py` passes all tests (8/8)
- [ ] Manual test: "Forecast next month's orders" works
- [ ] Manual test: "What are my sales trends?" works
- [ ] Logs show "analytics context generated"
- [ ] AI includes confidence levels in forecasts
- [ ] AI provides specific numbers (not vague)
- [ ] AI gives actionable recommendations

---

## 🎉 Summary

Your Goodyear RAG Agent now has **enterprise-grade analytical capabilities**:

✅ Intelligent trend analysis
✅ 3 forecasting methods
✅ Automatic metric calculations
✅ Business recommendations
✅ Manufacturing-specific insights

**Next Steps:**
1. Test with `python test_analytics.py`
2. Deploy enhanced files
3. Try example queries
4. Monitor and refine based on feedback

**Questions?**
- Review sample queries in this guide
- Check test_analytics.py for working examples
- Review instructions.txt for AI behavior details

---

**Version:** 2.0 with Analytics  
**Last Updated:** January 2026  
**Optimized For:** Manufacturing operations and forecasting