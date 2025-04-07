from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math

class Trader:
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }
    
    # Product-specific parameters
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": {
            "alpha": 0.2,           # Lower alpha for stable product
            "spread": 1,            # Tighter spread for stable product
            "volume_scale": 1.0     # Full capacity for stable product
        },
        "KELP": {
            "alpha": 0.3,           # Medium alpha for trending product
            "spread": 2,            # Medium spread for trending product
            "volume_scale": 0.8,    # Conservative volume due to trends
            "trend_threshold": 5    # Price difference threshold to detect trend
        },
        "SQUID_INK": {
            "alpha": 0.4,           # Higher alpha for volatile product
            "spread": 3,            # Wider spread for volatile product
            "volume_scale": 0.7,    # Lower volume for volatile product
            "pattern_length": 50    # Look back window for pattern detection
        }
    }
    
    def __init__(self):
        # Initialize historical data storage
        self.historical_prices = {}
        
    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])
    
    def get_product_params(self, product):
        """Gets the trading parameters for a given product."""
        return self.PRODUCT_PARAMS.get(product, {
            "alpha": 0.3,
            "spread": 2,
            "volume_scale": 0.8
        })
    
    def detect_trend(self, prices, product):
        """Detect trend direction and strength for a product."""
        if len(prices) < 5:
            return 0
        
        # Use short and long EMAs to detect trend
        short_window = min(len(prices), 5)
        long_window = min(len(prices), 15)
        
        short_avg = sum(prices[-short_window:]) / short_window
        long_avg = sum(prices[-long_window:]) / long_window
        
        params = self.get_product_params(product)
        threshold = params.get("trend_threshold", 5)
        
        if short_avg - long_avg > threshold:
            return 1  # Uptrend
        elif long_avg - short_avg > threshold:
            return -1  # Downtrend
        return 0  # No significant trend
    
    def detect_pattern(self, prices, product):
        """Detect cyclical patterns in price data."""
        if len(prices) < 10:
            return 0
        
        params = self.get_product_params(product)
        window = min(len(prices), params.get("pattern_length", 50))
        recent_prices = prices[-window:]
        
        # Simple pattern detection: looking at recent movements
        last_3 = recent_prices[-3:]
        
        # Check for potential turning points
        if last_3[0] > last_3[1] and last_3[1] < last_3[2]:
            return 1  # Potential bottom, good for buying
        elif last_3[0] < last_3[1] and last_3[1] > last_3[2]:
            return -1  # Potential top, good for selling
        
        return 0  # No clear pattern
    
    def run(self, state: TradingState):
        """
        Process TradingState with enhanced strategies.
        """
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}
            
        # Initialize price history and EMA if not present
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
            
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)
            
            # Skip if not enough orders to make a market
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
                
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            
            # Skip if market is crossed
            if best_bid >= best_ask:
                continue
                
            mid_price = (best_bid + best_ask) / 2
            
            # Update price history
            if product not in trader_data["price_history"]:
                trader_data["price_history"][product] = []
            trader_data["price_history"][product].append(mid_price)
            
            # Keep only the last 100 prices to manage memory
            trader_data["price_history"][product] = trader_data["price_history"][product][-100:]
            
            # Get product-specific parameters
            params = self.get_product_params(product)
            alpha = params["alpha"]
            base_spread = params["spread"]
            volume_scale = params["volume_scale"]
            
            # Calculate EMA
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = alpha * mid_price + (1 - alpha) * old_ema
                trader_data["ema_prices"][product] = new_ema
                
            ema_price = trader_data["ema_prices"][product]
            
            # Apply product-specific strategies
            if product == "RAINFOREST_RESIN":
                # Mean-reversion strategy for stable product
                # If price is below EMA, buy. If above EMA, sell.
                price_diff = mid_price - ema_price
                adjustment = min(abs(price_diff) / 2, base_spread)
                
                if price_diff < 0:  # Price below EMA, good time to buy
                    buy_price = math.floor(mid_price - base_spread + adjustment)
                    sell_price = math.ceil(mid_price + base_spread)
                else:  # Price above EMA, good time to sell
                    buy_price = math.floor(mid_price - base_spread)
                    sell_price = math.ceil(mid_price + base_spread - adjustment)
                    
            elif product == "KELP":
                # Trend-following strategy for trending product
                trend = self.detect_trend(trader_data["price_history"][product], product)
                
                # Adjust spread based on trend direction
                if trend > 0:  # Uptrend - buy more aggressively, sell less aggressively
                    buy_price = math.floor(mid_price - base_spread + 1)
                    sell_price = math.ceil(mid_price + base_spread + 1)
                    volume_scale = min(1.0, volume_scale + 0.1)  # Increase volume
                elif trend < 0:  # Downtrend - buy less aggressively, sell more aggressively
                    buy_price = math.floor(mid_price - base_spread - 1)
                    sell_price = math.ceil(mid_price + base_spread - 1)
                    volume_scale = max(0.5, volume_scale - 0.1)  # Decrease volume
                else:  # No clear trend
                    buy_price = math.floor(ema_price - base_spread)
                    sell_price = math.ceil(ema_price + base_spread)
                    
            elif product == "SQUID_INK":
                # Pattern-based strategy for cyclical product
                pattern = self.detect_pattern(trader_data["price_history"][product], product)
                
                # Adjust position based on detected pattern
                if pattern > 0:  # Potential bottom, good for buying
                    buy_price = math.floor(mid_price - base_spread + 1)
                    sell_price = math.ceil(mid_price + base_spread + 2)
                    volume_scale = min(1.0, volume_scale + 0.2)  # Increase buying volume
                elif pattern < 0:  # Potential top, good for selling
                    buy_price = math.floor(mid_price - base_spread - 2)
                    sell_price = math.ceil(mid_price + base_spread - 1)
                    volume_scale = max(0.5, volume_scale - 0.2)  # Decrease buying volume
                else:  # No clear pattern
                    # Default to a wider spread for volatile product
                    buy_price = math.floor(ema_price - base_spread)
                    sell_price = math.ceil(ema_price + base_spread)
            else:
                # Default strategy for unknown products
                buy_price = math.floor(ema_price - base_spread)
                sell_price = math.ceil(ema_price + base_spread)
                
            # Calculate volumes based on position limits and strategy
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position
            
            buy_volume = math.floor(max_buy_capacity * volume_scale)
            sell_volume = math.floor(max_sell_capacity * volume_scale)
            
            # Ensure minimum volume
            buy_volume = max(1, buy_volume)
            sell_volume = max(1, sell_volume)
            
            # Place buy order if our price is better than market ask
            if max_buy_capacity > 0 and buy_price < best_ask:
                orders.append(Order(product, buy_price, buy_volume))
                
            # Place sell order if our price is better than market bid
            if max_sell_capacity > 0 and sell_price > best_bid:
                orders.append(Order(product, sell_price, -sell_volume))
                
            if orders:
                result[product] = orders
                
        traderData = json.dumps(trader_data, separators=(',', ':'))
        conversions = 0
        
        return result, conversions, traderData