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
    
    # Enhanced product-specific parameters based on observed data
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": {
            "alpha": 0.15,           # Lower alpha for more stable EMA
            "spread": 2,             # Slightly wider spread for more profit
            "volume_scale": 1.0,     # Full capacity for stable product
            "min_profit_threshold": 2 # Minimum price difference for profitable trades
        },
        "KELP": {
            "alpha": 0.25,           # Adjusted alpha for better trend capture
            "spread": 2,             # Keep medium spread
            "volume_scale": 0.9,     # Increased volume for trending product
            "trend_threshold": 3,    # Lowered threshold to detect trends earlier
            "short_window": 5,       # Short EMA window
            "long_window": 15,       # Long EMA window
            "volume_adjustment": 0.2  # Volume adjustment based on trend strength
        },
        "SQUID_INK": {
            "alpha": 0.35,           # Adjusted alpha for volatile product
            "base_spread": 3,        # Base spread for volatile product
            "max_spread": 8,         # Maximum spread during high volatility
            "volume_scale": 0.75,    # Base volume for volatile product
            "pattern_length": 30,    # Shortened lookback window for faster pattern detection
            "volatility_window": 10, # Window for volatility calculation
            "min_volume": 5          # Minimum volume to trade
        }
    }
    
    def __init__(self):
        # Initialize historical data storage
        self.historical_prices = {}
        self.observed_volatility = {}
        self.last_trade_prices = {}
        self.profitable_trades = {}
        
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
    
    def calculate_volatility(self, prices, window=10):
        """Calculate recent price volatility."""
        if len(prices) < window:
            return 0
            
        recent_prices = prices[-window:]
        avg_price = sum(recent_prices) / len(recent_prices)
        squared_diffs = [(p - avg_price) ** 2 for p in recent_prices]
        variance = sum(squared_diffs) / len(squared_diffs)
        return math.sqrt(variance)
    
    def detect_trend(self, prices, product):
        """Enhanced trend detection with strength measurement."""
        if len(prices) < 5:
            return 0, 0
        
        params = self.get_product_params(product)
        short_window = min(len(prices), params.get("short_window", 5))
        long_window = min(len(prices), params.get("long_window", 15))
        
        short_avg = sum(prices[-short_window:]) / short_window
        long_avg = sum(prices[-long_window:]) / long_window
        
        threshold = params.get("trend_threshold", 3)
        price_diff = short_avg - long_avg
        
        # Calculate trend strength as a ratio of difference to threshold
        trend_strength = abs(price_diff) / threshold
        
        if price_diff > threshold:
            return 1, trend_strength  # Uptrend with strength
        elif price_diff < -threshold:
            return -1, trend_strength  # Downtrend with strength
        return 0, 0  # No significant trend
    
    def detect_pattern(self, prices, product):
        """Enhanced pattern detection with confidence level."""
        if len(prices) < 10:
            return 0, 0
        
        params = self.get_product_params(product)
        window = min(len(prices), params.get("pattern_length", 30))
        recent_prices = prices[-window:]
        
        # More sophisticated pattern detection
        if len(recent_prices) >= 5:
            last_5 = recent_prices[-5:]
            
            # Detect potential reversal patterns
            # V-shape bottom (buying opportunity)
            if last_5[0] > last_5[1] and last_5[1] > last_5[2] and last_5[2] < last_5[3] and last_5[3] < last_5[4]:
                confidence = (last_5[4] - last_5[2]) / last_5[2] * 100
                return 1, min(confidence, 1.0)  # Buy signal with confidence
                
            # Inverse V-shape top (selling opportunity)
            if last_5[0] < last_5[1] and last_5[1] < last_5[2] and last_5[2] > last_5[3] and last_5[3] > last_5[4]:
                confidence = (last_5[2] - last_5[4]) / last_5[2] * 100
                return -1, min(confidence, 1.0)  # Sell signal with confidence
        
        # Check for potential turning points with 3 points
        if len(recent_prices) >= 3:
            last_3 = recent_prices[-3:]
            
            # Potential bottom (buying opportunity)
            if last_3[0] > last_3[1] and last_3[1] < last_3[2]:
                confidence = (last_3[2] - last_3[1]) / last_3[1] * 100
                return 1, min(confidence/2, 0.7)  # Lower confidence for 3-point pattern
                
            # Potential top (selling opportunity)
            if last_3[0] < last_3[1] and last_3[1] > last_3[2]:
                confidence = (last_3[1] - last_3[2]) / last_3[1] * 100
                return -1, min(confidence/2, 0.7)  # Lower confidence for 3-point pattern
        
        return 0, 0  # No clear pattern
    
    def dynamic_spread_adjustment(self, product, volatility, trend_direction, mid_price):
        """Adjust spread based on volatility and trend direction."""
        params = self.get_product_params(product)
        base_spread = params.get("spread", params.get("base_spread", 2))
        
        # Calculate volatility component
        vol_adjustment = max(0, volatility - 2) if volatility > 2 else 0
        
        # Factor in trend direction - tighter spread when trading with trend
        trend_adjustment = 0
        if trend_direction != 0:
            # Tighten spread in direction of trend, widen in opposite
            trend_adjustment = -0.5 if trend_direction > 0 else 0.5
            
        final_spread = base_spread + vol_adjustment + trend_adjustment
        
        # Cap the spread to reasonable values
        max_spread = params.get("max_spread", 8)
        return min(max_spread, max(1, final_spread))
    
    def adjust_volume(self, base_volume, product, position, trend_dir, trend_strength, pattern_dir, pattern_confidence, volatility):
        """Dynamically adjust trading volume based on market conditions."""
        params = self.get_product_params(product)
        volume_scale = params.get("volume_scale", 0.8)
        position_limit = self.get_position_limit(product)
        
        # Start with base volume calculation
        adjusted_volume = base_volume * volume_scale
        
        # Position-based adjustment - be more conservative as we approach limits
        position_ratio = abs(position) / position_limit
        if position_ratio > 0.7:
            # Reduce volume when position is large
            adjusted_volume *= (1.0 - (position_ratio - 0.7) * 0.7)
        
        # Trend-based adjustment
        if trend_dir != 0 and trend_strength > 0:
            # Increase volume when trading with strong trend
            vol_adj = params.get("volume_adjustment", 0.2)
            if (trend_dir > 0 and position <= 0) or (trend_dir < 0 and position >= 0):
                adjusted_volume *= (1.0 + vol_adj * trend_strength)
            else:
                # Decrease volume when trading against trend
                adjusted_volume *= (1.0 - vol_adj * trend_strength)
        
        # Pattern-based adjustment
        if pattern_dir != 0 and pattern_confidence > 0:
            if (pattern_dir > 0 and position <= 0) or (pattern_dir < 0 and position >= 0):
                # Increase volume for high-confidence patterns in favorable direction
                adjusted_volume *= (1.0 + 0.3 * pattern_confidence)
        
        # Volatility adjustment - reduce volume in high volatility
        if volatility > 5:
            vol_factor = max(0.5, 1.0 - (volatility - 5) * 0.05)
            adjusted_volume *= vol_factor
        
        # Ensure minimum volume
        min_volume = params.get("min_volume", 1)
        return max(min_volume, math.floor(adjusted_volume))
    
    def opportunistic_orders(self, product, order_depth, current_position, position_limit, ema_price):
        """Generate opportunistic limit orders for significant price dislocations."""
        orders = []
        
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders
            
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        
        # Look for buying opportunities (significantly below EMA)
        if current_position < position_limit:
            buy_capacity = position_limit - current_position
            
            # Check for each bid level
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if bid_price < ema_price * 0.995:  # Price is 0.5% below EMA
                    discount_factor = min(1.0, (ema_price - bid_price) / ema_price * 20)
                    volume = min(abs(order_depth.buy_orders[bid_price]), 
                                math.floor(buy_capacity * discount_factor * 0.25))
                    
                    if volume > 0:
                        orders.append(Order(product, bid_price + 1, volume))
                        buy_capacity -= volume
        
        # Look for selling opportunities (significantly above EMA)
        if current_position > -position_limit:
            sell_capacity = position_limit + current_position
            
            # Check for each ask level
            for ask_price in sorted(order_depth.sell_orders.keys()):
                if ask_price > ema_price * 1.005:  # Price is 0.5% above EMA
                    premium_factor = min(1.0, (ask_price - ema_price) / ema_price * 20)
                    volume = min(order_depth.sell_orders[ask_price], 
                                math.floor(sell_capacity * premium_factor * 0.25))
                    
                    if volume > 0:
                        orders.append(Order(product, ask_price - 1, -volume))
                        sell_capacity -= volume
        
        return orders
    
    def run(self, state: TradingState):
        """
        Enhanced trading strategy with dynamic adjustment based on market conditions.
        """
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except json.JSONDecodeError:
            trader_data = {}
            
        # Initialize data structures
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "profit_per_product" not in trader_data:
            trader_data["profit_per_product"] = {}
            
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # Skip if no orders
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
                
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            
            # Skip if market is crossed
            if best_bid >= best_ask:
                continue
                
            mid_price = (best_bid + best_ask) / 2
            position_limit = self.get_position_limit(product)
            current_position = state.position.get(product, 0)
            
            # Update price history
            if product not in trader_data["price_history"]:
                trader_data["price_history"][product] = []
            trader_data["price_history"][product].append(mid_price)
            
            # Keep only the last 100 prices
            trader_data["price_history"][product] = trader_data["price_history"][product][-100:]
            
            # Get product-specific parameters
            params = self.get_product_params(product)
            alpha = params["alpha"]
            
            # Update EMA
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                new_ema = alpha * mid_price + (1 - alpha) * old_ema
                trader_data["ema_prices"][product] = new_ema
                
            ema_price = trader_data["ema_prices"][product]
            
            # Calculate volatility
            volatility = self.calculate_volatility(
                trader_data["price_history"][product], 
                params.get("volatility_window", 10)
            )
            trader_data["volatility"][product] = volatility
            
            # Detect market conditions
            trend_direction, trend_strength = self.detect_trend(
                trader_data["price_history"][product], product
            )
            
            pattern_direction, pattern_confidence = self.detect_pattern(
                trader_data["price_history"][product], product
            )
            
            # Dynamic spread based on volatility and trend
            dynamic_spread = self.dynamic_spread_adjustment(
                product, volatility, trend_direction, mid_price
            )
            
            # Product-specific strategies
            if product == "RAINFOREST_RESIN":
                # Enhanced mean-reversion strategy
                price_diff = mid_price - ema_price
                min_profit = params.get("min_profit_threshold", 2)
                
                # Adjust strategy based on price difference from EMA
                if abs(price_diff) > min_profit:
                    # Significant deviation - stronger mean reversion
                    adjustment = min(abs(price_diff) / 2, dynamic_spread)
                    
                    if price_diff < -min_profit:  # Price below EMA, good time to buy
                        buy_price = math.floor(mid_price - dynamic_spread + adjustment)
                        sell_price = math.ceil(mid_price + dynamic_spread)
                        # Increase buy volume, decrease sell volume
                        buy_modifier = 1.2
                        sell_modifier = 0.8
                    elif price_diff > min_profit:  # Price above EMA, good time to sell
                        buy_price = math.floor(mid_price - dynamic_spread)
                        sell_price = math.ceil(mid_price + dynamic_spread - adjustment)
                        # Decrease buy volume, increase sell volume
                        buy_modifier = 0.8
                        sell_modifier = 1.2
                    else:  # Around EMA
                        buy_price = math.floor(ema_price - dynamic_spread)
                        sell_price = math.ceil(ema_price + dynamic_spread)
                        buy_modifier = 1.0
                        sell_modifier = 1.0
                else:
                    # Close to EMA - standard market making
                    buy_price = math.floor(ema_price - dynamic_spread)
                    sell_price = math.ceil(ema_price + dynamic_spread)
                    buy_modifier = 1.0
                    sell_modifier = 1.0
                    
            elif product == "KELP":
                # Enhanced trend-following strategy
                # Use both trend and pattern signals
                combined_signal = trend_direction
                if abs(pattern_direction) > abs(combined_signal):
                    combined_signal = pattern_direction
                
                # Adjust prices based on trend/pattern direction
                if combined_signal > 0:  # Uptrend/bullish pattern - buy more aggressively
                    buy_price = math.floor(mid_price - dynamic_spread + 1)
                    sell_price = math.ceil(mid_price + dynamic_spread + 1)
                    buy_modifier = 1.1 + trend_strength * 0.2
                    sell_modifier = 0.9
                elif combined_signal < 0:  # Downtrend/bearish pattern - sell more aggressively
                    buy_price = math.floor(mid_price - dynamic_spread - 1)
                    sell_price = math.ceil(mid_price + dynamic_spread - 1)
                    buy_modifier = 0.9
                    sell_modifier = 1.1 + trend_strength * 0.2
                else:  # No clear direction
                    buy_price = math.floor(ema_price - dynamic_spread)
                    sell_price = math.ceil(ema_price + dynamic_spread)
                    buy_modifier = 1.0
                    sell_modifier = 1.0
                    
            elif product == "SQUID_INK":
                # Enhanced volatility strategy
                base_spread = params.get("base_spread", 3)
                
                # Wider spreads during high volatility
                actual_spread = base_spread + min(5, volatility / 2)
                
                # Adjust based on pattern detection
                if pattern_direction > 0:  # Potential bottom, good for buying
                    buy_price = math.floor(mid_price - actual_spread + pattern_confidence * 2)
                    sell_price = math.ceil(mid_price + actual_spread + 1)
                    buy_modifier = 1.0 + pattern_confidence * 0.3
                    sell_modifier = 0.8
                elif pattern_direction < 0:  # Potential top, good for selling
                    buy_price = math.floor(mid_price - actual_spread - 1)
                    sell_price = math.ceil(mid_price + actual_spread - pattern_confidence * 2)
                    buy_modifier = 0.8
                    sell_modifier = 1.0 + pattern_confidence * 0.3
                else:  # No clear pattern
                    # Default to a wider spread for volatile product
                    buy_price = math.floor(ema_price - actual_spread)
                    sell_price = math.ceil(ema_price + actual_spread)
                    buy_modifier = 1.0
                    sell_modifier = 1.0
                    
                # Add opportunistic orders for SQUID_INK due to its volatility
                opportunistic_orders = self.opportunistic_orders(
                    product, order_depth, current_position, position_limit, ema_price
                )
                orders.extend(opportunistic_orders)
            else:
                # Default strategy for unknown products
                buy_price = math.floor(ema_price - dynamic_spread)
                sell_price = math.ceil(ema_price + dynamic_spread)
                buy_modifier = 1.0
                sell_modifier = 1.0
                
            # Calculate volumes with dynamic adjustments
            max_buy_capacity = position_limit - current_position
            max_sell_capacity = position_limit + current_position
            
            # Adjust volumes based on market conditions
            buy_volume = self.adjust_volume(
                max_buy_capacity * buy_modifier,
                product, current_position,
                trend_direction, trend_strength,
                pattern_direction, pattern_confidence,
                volatility
            )
            
            sell_volume = self.adjust_volume(
                max_sell_capacity * sell_modifier,
                product, current_position,
                trend_direction, trend_strength,
                pattern_direction, pattern_confidence,
                volatility
            )
            
            # Ensure valid volumes
            buy_volume = min(max(1, buy_volume), max_buy_capacity)
            sell_volume = min(max(1, sell_volume), max_sell_capacity)
            
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