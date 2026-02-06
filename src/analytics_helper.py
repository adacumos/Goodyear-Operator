"""
Analytics Helper for Manufacturing Forecasting (FIXED)
Provides simple, explainable analytical functions for the AI agent
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)


class ManufacturingAnalytics:
    """
    Simple analytics helper that processes search results
    and provides trend analysis for forecasting
    """
    
    @staticmethod
    def extract_numeric_value(text: str, pattern: str = None) -> Optional[float]:
        """
        Extract numeric value from text, handling commas and currency symbols
        
        Args:
            text: Input text containing numbers
            pattern: Optional custom regex pattern
        
        Returns:
            First numeric value found, or None
        
        Examples:
            "Quantity: 500" -> 500.0
            "Price: $2,500.00" -> 2500.0
            "Growth of 15.5%" -> 15.5
        """
        # Remove currency symbols and clean the text
        cleaned_text = text.replace('$', '').replace(',', '')
        
        # Pattern matches: integer or decimal numbers
        if pattern is None:
            pattern = r'\d+\.?\d*'
        
        match = re.search(pattern, cleaned_text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None
    
    @staticmethod
    def extract_date(text: str) -> Optional[datetime]:
        """
        Extract date from common formats in search results
        
        Args:
            text: Text containing date (e.g., "2026-01-15" or "January 15, 2026")
        
        Returns:
            Datetime object or None
        """
        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%B %d, %Y',
            '%b %d, %Y'
        ]
        
        for fmt in formats:
            try:
                # Find date-like patterns
                if fmt == '%Y-%m-%d':
                    match = re.search(r'\d{4}-\d{2}-\d{2}', text)
                elif fmt in ['%m/%d/%Y']:
                    match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
                else:
                    # For named months, try to find the full date string
                    match = re.search(r'[A-Z][a-z]+ \d{1,2}, \d{4}', text)
                
                if match:
                    date_str = match.group()
                    return datetime.strptime(date_str, fmt)
            except (ValueError, AttributeError):
                continue
        
        return None
    
    @staticmethod
    def calculate_moving_average(values: List[float], window: int = 3) -> Optional[float]:
        """
        Calculate simple moving average
        
        Args:
            values: List of numeric values
            window: Number of periods to average
        
        Returns:
            Moving average or None if insufficient data
        """
        if not values or len(values) < window:
            return None
        
        recent_values = values[-window:]
        return sum(recent_values) / len(recent_values)
    
    @staticmethod
    def calculate_growth_rate(old_value: float, new_value: float) -> Optional[float]:
        """
        Calculate percentage growth rate
        
        Args:
            old_value: Earlier value
            new_value: Later value
        
        Returns:
            Growth rate as percentage (e.g., 15.5 for 15.5% growth)
        """
        if old_value == 0:
            return None
        
        return ((new_value - old_value) / old_value) * 100
    
    @staticmethod
    def simple_linear_forecast(
        values: List[float], 
        periods_ahead: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Simple linear trend forecasting
        Uses average growth rate for projection
        
        Args:
            values: Historical values (chronologically ordered)
            periods_ahead: Number of periods to forecast
        
        Returns:
            Dictionary with forecast and confidence info
        """
        if not values or len(values) < 2:
            return None
        
        # Calculate average growth rate
        growth_rates = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                rate = (values[i] - values[i-1]) / values[i-1]
                growth_rates.append(rate)
        
        if not growth_rates:
            return None
        
        avg_growth = sum(growth_rates) / len(growth_rates)
        last_value = values[-1]
        
        # Project forward
        forecast = last_value * (1 + avg_growth) ** periods_ahead
        
        # Calculate simple confidence based on consistency
        std_dev = (sum((r - avg_growth) ** 2 for r in growth_rates) / len(growth_rates)) ** 0.5
        confidence = "high" if std_dev < 0.1 else "medium" if std_dev < 0.3 else "low"
        
        return {
            'forecast_value': round(forecast, 2),
            'avg_growth_rate': round(avg_growth * 100, 2),  # As percentage
            'confidence': confidence,
            'base_value': last_value,
            'periods_analyzed': len(values)
        }
    
    @staticmethod
    def analyze_search_results(search_output: str) -> Dict[str, Any]:
        """
        Analyze search results to extract analytical insights
        
        Args:
            search_output: Formatted search results from Azure AI Search
        
        Returns:
            Dictionary with extracted analytics
        """
        analysis = {
            'order_count': 0,
            'unique_customers': set(),
            'total_quantities': [],
            'dates': [],
            'prices': [],
            'record_types': defaultdict(int)
        }
        
        # Split into individual records
        chunks = search_output.split('---')
        
        for chunk in chunks:
            # Count record types
            if 'Record Type: Historical Order' in chunk:
                analysis['record_types']['Historical'] += 1
            elif 'Record Type: Open Order' in chunk:
                analysis['record_types']['OpenOrder'] += 1
            elif 'Record Type: Shipment' in chunk:
                analysis['record_types']['Shipment'] += 1
            
            # Extract customer info
            customer_match = re.search(r'Customer Name: ([^.]+)', chunk)
            if customer_match:
                analysis['unique_customers'].add(customer_match.group(1).strip())
            
            # Extract order numbers (count unique orders)
            order_match = re.search(r'Order #: ([^.]+)', chunk)
            if order_match:
                analysis['order_count'] += 1
            
            # Extract quantities - FIXED: Remove commas before parsing
            qty_match = re.search(r'Quantity (?:Shipped|Ordered): ([\d,]+\.?\d*)', chunk)
            if qty_match:
                qty_str = qty_match.group(1).replace(',', '')  # Remove commas
                try:
                    qty = float(qty_str)
                    analysis['total_quantities'].append(qty)
                except ValueError:
                    logger.warning(f"Could not parse quantity: {qty_match.group(1)}")
            
            # Extract prices - FIXED: Handle currency formatting
            price_match = re.search(r'Price: \$([\d,]+\.?\d*)', chunk)
            if price_match:
                price_str = price_match.group(1).replace(',', '')  # Remove commas
                try:
                    price = float(price_str)
                    analysis['prices'].append(price)
                except ValueError:
                    logger.warning(f"Could not parse price: {price_match.group(1)}")
            
            # Extract dates
            date = ManufacturingAnalytics.extract_date(chunk)
            if date:
                analysis['dates'].append(date)
        
        # Convert set to count
        analysis['unique_customers'] = len(analysis['unique_customers'])
        
        # Calculate aggregates
        if analysis['total_quantities']:
            analysis['total_quantity'] = sum(analysis['total_quantities'])
            analysis['avg_quantity'] = sum(analysis['total_quantities']) / len(analysis['total_quantities'])
        
        if analysis['prices']:
            analysis['total_revenue'] = sum(analysis['prices'])
            analysis['avg_price'] = sum(analysis['prices']) / len(analysis['prices'])
        
        # Sort dates for trend analysis
        if analysis['dates']:
            analysis['dates'].sort()
            analysis['date_range'] = {
                'earliest': analysis['dates'][0].strftime('%Y-%m-%d'),
                'latest': analysis['dates'][-1].strftime('%Y-%m-%d')
            }
        
        return analysis
    
    @staticmethod
    def generate_forecast_insight(analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable forecast insight
        
        Args:
            analysis: Analysis dictionary from analyze_search_results
        
        Returns:
            Natural language insight text
        """
        insights = []
        
        # Order trends
        if analysis.get('order_count', 0) > 0:
            insights.append(f"Analyzed {analysis['order_count']} orders")
        
        # Customer insights
        if analysis.get('unique_customers', 0) > 0:
            insights.append(f"across {analysis['unique_customers']} unique customers")
        
        # Revenue insights
        if analysis.get('total_revenue'):
            total_rev = analysis['total_revenue']
            avg_rev = analysis.get('avg_price', 0)
            insights.append(
                f"Total revenue: ${total_rev:,.2f} (avg ${avg_rev:,.2f} per order)"
            )
        
        # Volume insights
        if analysis.get('total_quantity'):
            total_qty = analysis['total_quantity']
            avg_qty = analysis.get('avg_quantity', 0)
            insights.append(
                f"Total quantity: {total_qty:,.0f} units (avg {avg_qty:,.0f} per order)"
            )
        
        # Time range
        if analysis.get('date_range'):
            dr = analysis['date_range']
            insights.append(f"Date range: {dr['earliest']} to {dr['latest']}")
        
        # Forecast if we have historical data
        if analysis.get('total_quantities') and len(analysis['total_quantities']) >= 3:
            forecast = ManufacturingAnalytics.simple_linear_forecast(
                analysis['total_quantities'], 
                periods_ahead=1
            )
            if forecast:
                insights.append(
                    f"Forecast (next period): {forecast['forecast_value']:,.0f} units "
                    f"({forecast['avg_growth_rate']:+.1f}% trend, {forecast['confidence']} confidence)"
                )
        
        return ". ".join(insights) + "." if insights else "Insufficient data for analysis."


def create_analytics_context(search_output: str) -> str:
    """
    Main function to create analytics context for the AI
    
    Args:
        search_output: Raw search results from Azure AI Search
    
    Returns:
        Formatted analytics context to add to AI prompt
    """
    if not search_output or len(search_output.strip()) < 50:
        return ""
    
    try:
        analytics = ManufacturingAnalytics()
        analysis = analytics.analyze_search_results(search_output)
        insight = analytics.generate_forecast_insight(analysis)
        
        context = f"""

📊 ANALYTICAL SUMMARY (Auto-generated from search results):
{insight}

💡 KEY METRICS:
- Record Types: {dict(analysis.get('record_types', {}))}
- Unique Customers: {analysis.get('unique_customers', 0)}
- Total Orders: {analysis.get('order_count', 0)}

Use these insights to provide intelligent forecasts and recommendations.
"""
        
        logger.info(f"Generated analytics context: {len(context)} chars")
        return context
        
    except Exception as e:
        logger.error(f"Analytics context generation failed: {e}")
        return ""