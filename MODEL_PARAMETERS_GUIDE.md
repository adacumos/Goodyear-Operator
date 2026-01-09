# Model Parameters Configuration Guide

## Quick Start

1. **Create the custom model file**: Save the `custom_ai_model.py` file in your project root
2. **Update app.py**: Replace the model initialization with the new factory function
3. **Adjust parameters**: Modify the values in `create_model_from_config()` based on your needs

## Understanding Model Parameters

### Temperature (0.0 - 2.0)
**What it does:** Controls randomness in responses

- **0.0 - 0.3**: Highly deterministic, focused, factual
  - ✅ Use for: Order status, data retrieval, factual queries
  - ❌ Avoid for: Creative writing, brainstorming
  
- **0.4 - 0.7**: Balanced creativity and consistency
  - ✅ Use for: General conversation, customer service
  
- **0.8 - 2.0**: Highly creative, more random
  - ✅ Use for: Creative tasks, ideation
  - ❌ Avoid for: Factual corporate data

**Recommended for Goodyear Assistant:** `0.3` (precise, factual responses)

---

### Max Tokens (1 - 4096+)
**What it does:** Maximum length of the response

- **500 - 1000**: Short, concise answers
- **1500 - 2000**: Detailed explanations with examples
- **2500+**: Long-form content, multiple tables

**Recommended for Goodyear Assistant:** `2000` (allows detailed order breakdowns with tables)

---

### Top P (0.0 - 1.0)
**What it does:** Nucleus sampling - considers only top probability tokens

- **0.9 - 1.0**: More diverse word choices
- **0.5 - 0.8**: More focused, conservative choices

**Recommended for Goodyear Assistant:** `0.9` (slightly focused but natural)

---

### Frequency Penalty (-2.0 to 2.0)
**What it does:** Reduces repetition of token sequences

- **0.0**: No penalty
- **0.5 - 1.0**: Moderate reduction in repetition
- **1.5+**: Strong avoidance of repetition (may affect clarity)

**Recommended for Goodyear Assistant:** `0.2` (allows necessary repetition for clarity)

---

### Presence Penalty (-2.0 to 2.0)
**What it does:** Encourages talking about new topics

- **0.0**: No penalty
- **0.5 - 1.0**: Encourages topic variety
- **1.5+**: Strong push for new topics

**Recommended for Goodyear Assistant:** `0.1` (slight variety without losing focus)

---

## Usage Examples

### Example 1: Precise Corporate Assistant (Current Configuration)
```python
model = create_model_from_config(
    temperature=0.3,        # Very focused and factual
    max_tokens=2000,        # Detailed responses
    top_p=0.9,
    frequency_penalty=0.2,
    presence_penalty=0.1
)
```

### Example 2: More Conversational Assistant
```python
model = create_model_from_config(
    temperature=0.7,        # More natural variation
    max_tokens=1500,
    top_p=0.95,
    frequency_penalty=0.5,  # Reduce repetition
    presence_penalty=0.3
)
```

### Example 3: Concise Response Mode
```python
model = create_model_from_config(
    temperature=0.4,
    max_tokens=800,         # Shorter responses
    top_p=0.9,
    frequency_penalty=0.3,
    presence_penalty=0.0
)
```

---

## Dynamic Parameter Updates

You can change parameters during runtime:

```python
# Check current settings
print(model.get_parameters())

# Update for a specific use case
model.update_parameters(temperature=0.5, max_tokens=1000)

# Reset to defaults
model.update_parameters(
    temperature=0.3,
    max_tokens=2000
)
```

---

## Testing Different Configurations

### For Factual Data Retrieval (Order Status, Inventory)
- Temperature: **0.2 - 0.4**
- Max Tokens: **1500 - 2000**
- Top P: **0.85 - 0.95**

### For Customer Explanations (Why is this backordered?)
- Temperature: **0.5 - 0.7**
- Max Tokens: **1000 - 1500**
- Top P: **0.9 - 1.0**

### For Data Analysis (Summarize trends)
- Temperature: **0.4 - 0.6**
- Max Tokens: **2000 - 3000**
- Top P: **0.9**

---

## Troubleshooting

### Problem: Responses are too repetitive
**Solution:** Increase `frequency_penalty` to 0.5 - 0.8

### Problem: Responses are too random/inconsistent
**Solution:** Lower `temperature` to 0.2 - 0.4

### Problem: Responses cut off mid-sentence
**Solution:** Increase `max_tokens` to 2000+

### Problem: Responses are too verbose
**Solution:** Lower `max_tokens` to 1000 - 1200 and add "Be concise" to instructions

### Problem: Model ignores context from search
**Solution:** Lower `temperature` to 0.3 and ensure search results are clearly formatted

---

## File Structure

```
your-project/
├── app.py                          # Updated with custom model
├── custom_ai_model.py              # New file - model wrapper
├── azure_ai_search_data_source.py  # Existing
├── config.py                       # Existing
├── instructions.txt                # Existing
├── requirements.txt                # Existing
└── MODEL_PARAMETERS_GUIDE.md       # This guide
```

---

## Additional Notes

- **Always test** parameter changes with real queries from your stakeholders
- **Monitor feedback** using the Teams feedback mechanism
- **Document** any parameter changes you make for your specific use case
- **Start conservative** (low temperature) and increase if needed