
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
    
    # Enhanced product-specific parameters with wider ranges
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": {
            "alpha": 0.18,           # Slightly increased for better responsiveness
            "spread": 2,             # Keep current spread
            "volume_scale": 1.2,     # Increased volume for more profit opportunity
            "min_profit_threshold": 1.5, # Lower threshold to catch more opportunities
            "max_position_ratio": 0.9,  # Allow using up to 90% of position limit
            "volatility_threshold": 3   # Threshold for considering market volatile
        },
        "KELP": {
            "alpha": 0.22,           # Fine-tuned alpha
            "spread": 2,             # Keep current spread
            "volume_scale": 1.1,     # Increased volume
            "trend_threshold": 2.5,  # Lower threshold for faster trend detection
            "short_window": 4,       # Shorter window for faster response
            "long_window": 12,       # Shorter long window
            "volume_adjustment": 0.25,# Higher volume adjustment for stronger trends
            "reversal_threshold": 4  # Threshold for trend reversal detection
        },
        "SQUID_INK": {
            "alpha": 0.38,           # More responsive for volatile market
            "base_spread": 3,        # Keep base spread
            "max_spread": 9,         # Slightly increased max spread
            "volume_scale": 0.9,     # Increased base volume
            "pattern_length": 25,    # Optimized lookback window
            "volatility_window": 8,  # Shorter volatility window
            "min_volume": 6,         # Increased minimum volume
            "opp_threshold": 0.008   # Threshold for opportunistic trades (0.8%)
        }
    }
    
    def __init__(self):
        # Enhanced historical data storage
        self.historical_prices = {}
        self.observed_volatility = {}
        self.last_trade_prices = {}
        self.profitable_trades = {}
        self.product_performance = {}  # Track performance per product
        self.trade_history = {}        # Track all trades
        
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
        """Calculate recent price volatility with exponential weighting."""
        if len(prices) < window:
            return 0
            
        recent_prices = prices[-window:]
        # Apply exponential weighting - recent volatility matters more
        weights = [math.exp(i/5) for i in range(len(recent_prices))]
        norm_weights = [w/sum(weights) for w in weights]
        
        avg_price = sum(p*w for p,w in zip(recent_prices, norm_weights))
        squared_diffs = [(p - avg_price) ** 2 for p in recent_prices]
        weighted_variance = sum(sd*w for sd,w in zip(squared_diffs, norm_weights))
        return math.sqrt(weighted_variance)
    
    def detect_trend(self, prices, product, volumes=None):
        """Enhanced trend detection with volume confirmation."""
        if len(prices) < 5:
            return 0, 0
        
        params = self.get_product_params(product)
        short_window = min(len(prices), params.get("short_window", 4))
        long_window = min(len(prices), params.get("long_window", 12))
        
        # Exponential weighted moving averages
        short_weights = [math.exp(i/2) for i in range(short_window)]
        short_weights = [w/sum(short_weights) for w in short_weights]
        short_avg = sum(p*w for p,w in zip(prices[-short_window:], short_weights))
        
        long_weights = [math.exp(i/4) for i in range(long_window)]
        long_weights = [w/sum(long_weights) for w in long_weights]
        long_avg = sum(p*w for p,w in zip(prices[-long_window:], long_weights))
        
        threshold = params.get("trend_threshold", 2.5)
        price_diff = short_avg - long_avg
        
        # Calculate momentum
        if len(prices) >= 3:
            momentum = prices[-1] - prices[-3]
        else:
            momentum = 0
            
        # Calculate trend strength with momentum component
        trend_strength = (abs(price_diff) / threshold) + (abs(momentum) / threshold / 2)
        
        # Check for trend reversal
        reversal_threshold = params.get("reversal_threshold", 4)
        if len(prices) >= reversal_threshold:
            recent = prices[-reversal_threshold//2:]
            prior = prices[-reversal_threshold:-reversal_threshold//2]
            recent_trend = sum(recent) / len(recent) - recent[0]
            prior_trend = sum(prior) / len(prior) - prior[0]
            
            # If trends in opposite directions and significant
            if recent_trend * prior_trend < 0 and abs(recent_trend) > threshold/2 and abs(prior_trend) > threshold/2:
                # Reduce strength, potential reversal
                trend_strength *= 0.5
        
        if price_diff > threshold:
            return 1, trend_strength  # Uptrend with strength
        elif price_diff < -threshold:
            return -1, trend_strength  # Downtrend with strength
        return 0, 0  # No significant trend
    
    def detect_pattern(self, prices, product):
        """Enhanced pattern detection with more complex patterns."""
        if len(prices) < 10:
            return 0, 0
        
        params = self.get_product_params(product)
        window = min(len(prices), params.get("pattern_length", 25))
        recent_prices = prices[-window:]
        
        # Basic patterns
        basic_pattern, basic_conf = self._detect_basic_pattern(recent_prices)
        
        # Complex patterns detection
        if len(recent_prices) >= 8:
            # Detect double bottom/top patterns
            double_pattern, double_conf = self._detect_double_pattern(recent_prices)
            
            # Return the stronger signal
            if double_conf > basic_conf:
                return double_pattern, double_conf
        
        # Head and shoulders pattern (simplified)
        if len(recent_prices) >= 10:
            hs_pattern, hs_conf = self._detect_head_shoulders(recent_prices)
            if hs_conf > basic_conf:
                return hs_pattern, hs_conf
                
        return basic_pattern, basic_conf
    
    def _detect_basic_pattern(self, prices):
        """Detect basic V and inverted V patterns."""
        if len(prices) < 5:
            return 0, 0
            
        last_5 = prices[-5:]
        
        # V-shape bottom (buying opportunity)
        if last_5[0] > last_5[1] and last_5[1] > last_5[2] and last_5[2] < last_5[3] and last_5[3] < last_5[4]:
            depth = min(last_5[0], last_5[4]) - last_5[2]
            confidence = min(depth / last_5[2] * 150, 1.0)
            return 1, confidence  # Buy signal with confidence
            
        # Inverse V-shape top (selling opportunity)
        if last_5[0] < last_5[1] and last_5[1] < last_5[2] and last_5[2] > last_5[3] and last_5[3] > last_5[4]:
            height = last_5[2] - max(last_5[0], last_5[4])
            confidence = min(height / last_5[2] * 150, 1.0)
            return -1, confidence  # Sell signal with confidence
        
        # Check for potential turning points with 3 points
        if len(prices) >= 3:
            last_3 = prices[-3:]
            
            # Potential bottom (buying opportunity)
            if last_3[0] > last_3[1] and last_3[1] < last_3[2]:
                confidence = min((last_3[2] - last_3[1]) / last_3[1] * 120, 0.8)
                return 1, confidence
                
            # Potential top (selling opportunity)
            if last_3[0] < last_3[1] and last_3[1] > last_3[2]:
                confidence = min((last_3[1] - last_3[2]) / last_3[1] * 120, 0.8)
                return -1, confidence
                
        return 0, 0
    
    def _detect_double_pattern(self, prices):
        """Detect double bottom/top patterns."""
        if len(prices) < 8:
            return 0, 0
            
        # Simplify to key points to detect pattern
        highs_lows = self._find_local_extrema(prices)
        
        # Need at least 5 points for double bottom/top
        if len(highs_lows) < 5:
            return 0, 0
            
        # Check for double bottom (W shape)
        # Low - High - Low - High sequence with similar lows
        for i in range(len(highs_lows) - 4):
            p1, p2, p3, p4, p5 = highs_lows[i:i+5]
            
            # Double bottom pattern 
            if p1[1] == 'low' and p2[1] == 'high' and p3[1] == 'low' and p4[1] == 'high' and p5[1] == 'high':
                # Check if lows are at similar levels
                if abs(p1[0] - p3[0]) / p1[0] < 0.03:  # Within 3%
                    # Measure strength by height of recovery
                    strength = (p5[0] - min(p1[0], p3[0])) / min(p1[0], p3[0])
                    return 1, min(strength * 0.8, 0.9)  # Buy signal
        
        # Check for double top (M shape)
        # High - Low - High - Low sequence with similar highs
        for i in range(len(highs_lows) - 4):
            p1, p2, p3, p4, p5 = highs_lows[i:i+5]
            
            # Double top pattern
            if p1[1] == 'high' and p2[1] == 'low' and p3[1] == 'high' and p4[1] == 'low' and p5[1] == 'low':
                # Check if highs are at similar levels
                if abs(p1[0] - p3[0]) / p1[0] < 0.03:  # Within 3%
                    # Measure strength by depth of drop
                    strength = (max(p1[0], p3[0]) - p5[0]) / max(p1[0], p3[0])
                    return -1, min(strength * 0.8, 0.9)  # Sell signal
                    
        return 0, 0
    
    def _detect_head_shoulders(self, prices):
        """Detect head and shoulders pattern (or inverse)."""
        if len(prices) < 10:
            return 0, 0
            
        # Find local extrema
        highs_lows = self._find_local_extrema(prices)
        
        if len(highs_lows) < 7:
            return 0, 0
            
        # Look for sequences that could form head and shoulders
        for i in range(len(highs_lows) - 6):
            # Head and shoulders top pattern: high-low-higher high-low-lower high-low
            # Check for 'high' points forming the pattern
            if (highs_lows[i][1] == 'high' and 
                highs_lows[i+2][1] == 'high' and 
                highs_lows[i+4][1] == 'high'):
                
                # Check center peak (head) is higher than shoulders
                left_shoulder = highs_lows[i][0]
                head = highs_lows[i+2][0]
                right_shoulder = highs_lows[i+4][0]
                
                if head > left_shoulder and head > right_shoulder:
                    # Check shoulders are roughly at same level
                    if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                        # Calculate strength based on formation height
                        neckline = min(highs_lows[i+1][0], highs_lows[i+3][0])
                        strength = (head - neckline) / head
                        return -1, min(strength * 0.85, 0.95)  # Strong sell signal
            
            # Inverse head and shoulders: low-high-lower low-high-higher low-high
            if (highs_lows[i][1] == 'low' and 
                highs_lows[i+2][1] == 'low' and 
                highs_lows[i+4][1] == 'low'):
                
                # Check center trough (head) is lower than shoulders
                left_shoulder = highs_lows[i][0]
                head = highs_lows[i+2][0]
                right_shoulder = highs_lows[i+4][0]
                
                if head < left_shoulder and head < right_shoulder:
                    # Check shoulders are roughly at same level
                    if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                        # Calculate strength based on formation depth
                        neckline = max(highs_lows[i+1][0], highs_lows[i+3][0])
                        strength = (neckline - head) / head
                        return 1, min(strength * 0.85, 0.95)  # Strong buy signal
                        
        return 0, 0
    
    def _find_local_extrema(self, prices):
        """Find local maxima and minima in price series."""
        result = []
        
        # Need at least 3 points to find extrema
        if len(prices) < 3:
            return result
            
        # Check first point
        if prices[0] < prices[1]:
            result.append((prices[0], 'low'))
        elif prices[0] > prices[1]:
            result.append((prices[0], 'high'))
            
        # Check middle points
        for i in range(1, len(prices)-1):
            if prices[i-1] > prices[i] and prices[i] < prices[i+1]:
                result.append((prices[i], 'low'))
            elif prices[i-1] < prices[i] and prices[i] > prices[i+1]:
                result.append((prices[i], 'high'))
                
        # Check last point
        if prices[-2] < prices[-1]:
            result.append((prices[-1], 'high'))
        elif prices[-2] > prices[-1]:
            result.append((prices[-1], 'low'))
            
        return result
    
    def dynamic_spread_adjustment(self, product, volatility, trend_direction, mid_price, ema_price):
        """Advanced spread adjustment incorporating price trend and volatility."""
        params = self.get_product_params(product)
        base_spread = params.get("spread", params.get("base_spread", 2))
        
        # Start with volatility component
        vol_adjustment = max(0, volatility - 1.5) * 0.6
        
        # Price deviation from EMA component
        ema_deviation = abs(mid_price - ema_price) / ema_price
        ema_adjustment = ema_deviation * 15  # Scale up the effect
        
        # Trend component - tighten spread in trend direction for more fills
        trend_adjustment = 0
        if trend_direction != 0:
            # Tighten spread in direction of trend, widen in opposite
            trend_adjustment = -0.7 if abs(trend_direction) > 0.5 else -0.3
            
        # Combine adjustments
        final_spread = base_spread + vol_adjustment + ema_adjustment + trend_adjustment
        
        # Cap the spread to reasonable values
        max_spread = params.get("max_spread", 8)
        return min(max_spread, max(1, final_spread))
    
    def adjust_volume(self, base_volume, product, position, trend_dir, trend_strength, 
                     pattern_dir, pattern_confidence, volatility, profit_history=None):
        """Sophisticated volume adjustment based on multiple factors including profit history."""
        params = self.get_product_params(product)
        volume_scale = params.get("volume_scale", 0.8)
        position_limit = self.get_position_limit(product)
        
        # Start with base volume calculation
        adjusted_volume = base_volume * volume_scale
        
        # Position-based adjustment - more conservative as we approach limits
        position_ratio = abs(position) / position_limit
        max_position_ratio = params.get("max_position_ratio", 0.9)
        
        if position_ratio > max_position_ratio:
            # Strong reduction as position approaches limit
            position_scale = 1.0 - ((position_ratio - max_position_ratio) / (1 - max_position_ratio))
            adjusted_volume *= position_scale
        
        # Trend-based adjustment with enhanced sensitivity
        if trend_dir != 0 and trend_strength > 0:
            vol_adj = params.get("volume_adjustment", 0.25)
            if (trend_dir > 0 and position <= 0) or (trend_dir < 0 and position >= 0):
                # Trading with trend from neutral/opposite position
                adjusted_volume *= (1.0 + vol_adj * trend_strength * 1.2)
            elif (trend_dir > 0 and position > 0) or (trend_dir < 0 and position < 0):
                # Already have position in trend direction - be more conservative
                adjusted_volume *= (1.0 + vol_adj * trend_strength * 0.5)
            else:
                # Trading against trend
                adjusted_volume *= (1.0 - vol_adj * trend_strength * 0.8)
        
        # Pattern-based adjustment with confidence weighting
        if pattern_dir != 0 and pattern_confidence > 0:
            pattern_adj = 0.3 * pattern_confidence
            if (pattern_dir > 0 and position <= 0) or (pattern_dir < 0 and position >= 0):
                adjusted_volume *= (1.0 + pattern_adj * 1.3)
            else:
                adjusted_volume *= (1.0 - pattern_adj * 0.7)
        
        # Volatility adjustment - reduce volume in high volatility unless trading with clear signals
        vol_threshold = params.get("volatility_threshold", 3)
        if volatility > vol_threshold:
            # Check if we have clear signals supporting the trade
            signal_strength = 0
            if trend_dir != 0 and pattern_dir != 0:
                # Both trend and pattern agree
                if trend_dir == pattern_dir:
                    signal_strength = 0.7
                    
            # Adjust volume based on volatility and signal clarity
            vol_factor = max(0.4, 1.0 - (volatility - vol_threshold) * 0.08 * (1 - signal_strength))
            adjusted_volume *= vol_factor
        
        # Profit history based adjustment (if available)
        if profit_history and len(profit_history) > 0:
            recent_profits = profit_history[-5:]
            if sum(recent_profits) > 0:
                # Recent trading has been profitable - slightly increase volume
                profit_factor = min(1.3, 1.0 + (sum(recent_profits) / len(recent_profits)) * 0.02)
                adjusted_volume *= profit_factor
            elif sum(recent_profits) < 0:
                # Recent trading has been unprofitable - reduce volume
                loss_factor = max(0.7, 1.0 + (sum(recent_profits) / len(recent_profits)) * 0.04)
                adjusted_volume *= loss_factor
        
        # Ensure minimum volume
        min_volume = params.get("min_volume", 1)
        return max(min_volume, math.floor(adjusted_volume))
    
    def opportunistic_orders(self, product, order_depth, current_position, position_limit, ema_price):
        """Advanced opportunistic order generator for significant dislocations."""
        orders = []
        params = self.get_product_params(product)
        
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders
            
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid_price = (best_bid + best_ask) / 2
        
        # Threshold for opportunistic trades
        opp_threshold = params.get("opp_threshold", 0.008)  # 0.8% dislocation
        
        # Look for buying opportunities (significantly below EMA)
        if current_position < position_limit:
            buy_capacity = position_limit - current_position
            
            # Check for each bid level
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                # Calculate price dislocation relative to EMA
                dislocation = (ema_price - bid_price) / ema_price
                
                if dislocation > opp_threshold:
                    # Scale factor based on how severe the dislocation is
                    discount_factor = min(1.5, dislocation * 20)
                    
                    # More aggressive volume for larger dislocations
                    volume = min(abs(order_depth.buy_orders[bid_price]), 
                                math.floor(buy_capacity * discount_factor * 0.3))
                    
                    if volume > 0:
                        # Place order slightly above the current bid
                        orders.append(Order(product, bid_price + 1, volume))
                        buy_capacity -= volume
        
        # Look for selling opportunities (significantly above EMA)
        if current_position > -position_limit:
            sell_capacity = position_limit + current_position
            
            # Check for each ask level
            for ask_price in sorted(order_depth.sell_orders.keys()):
                # Calculate price dislocation relative to EMA
                dislocation = (ask_price - ema_price) / ema_price
                
                if dislocation > opp_threshold:
                    # Scale factor based on how severe the dislocation is
                    premium_factor = min(1.5, dislocation * 20)
                    
                    # More aggressive volume for larger dislocations
                    volume = min(order_depth.sell_orders[ask_price], 
                                math.floor(sell_capacity * premium_factor * 0.3))
                    
                    if volume > 0:
                        # Place order slightly below the current ask
                        orders.append(Order(product, ask_price - 1, -volume))
                        sell_capacity -= volume
        
        return orders
    
    def dynamic_price_levels(self, mid_price, ema_price, dynamic_spread, product, trend_dir, pattern_dir):
        """Calculate optimal price levels based on market conditions."""
        # Start with basic levels around EMA with dynamic spread
        base_buy = math.floor(mid_price - dynamic_spread)
        base_sell = math.ceil(mid_price + dynamic_spread)
        
        # Adjust based on EMA deviation
        ema_deviation = mid_price - ema_price
        ema_adjustment = abs(ema_deviation) * 0.3  # Scale the adjustment
        
        # Trend and pattern adjustment
        signal_dir = 0
        if trend_dir != 0 and pattern_dir != 0 and trend_dir == pattern_dir:
            # Strong signal when trend and pattern agree
            signal_dir = trend_dir
        elif trend_dir != 0:
            # Moderate signal from trend
            signal_dir = trend_dir * 0.7
        elif pattern_dir != 0:
            # Moderate signal from pattern
            signal_dir = pattern_dir * 0.6
            
        # Apply adjustments to prices
        if ema_deviation > 0:  # Current price above EMA
            # Make buy more conservative, sell more aggressive
            buy_price = math.floor(base_buy - ema_adjustment)
            sell_price = math.ceil(base_sell - ema_adjustment * 0.5)
        else:  # Current price below EMA
            # Make buy more aggressive, sell more conservative
            buy_price = math.floor(base_buy + ema_adjustment * 0.5)
            sell_price = math.ceil(base_sell + ema_adjustment)
            
        # Final adjustment based on combined signals
        if signal_dir > 0:  # Bullish signals
            buy_price = math.floor(buy_price + signal_dir * 0.8)
            sell_price = math.ceil(sell_price + signal_dir * 0.6)
        elif signal_dir < 0:  # Bearish signals
            buy_price = math.floor(buy_price + signal_dir * 0.6)
            sell_price = math.ceil(sell_price + signal_dir * 0.8)
            
        return buy_price, sell_price
    
    def run(self, state: TradingState):
        """
        Fully optimized trading strategy with dynamic adjustment and advanced analysis.
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
        if "trade_history" not in trader_data:
            trader_data["trade_history"] = {}
            
        # Update profit tracking
        for product, executed_trades in state.own_trades.items():
            if product not in trader_data["profit_per_product"]:
                trader_data["profit_per_product"][product] = []
                
            # Calculate profit from recent trades
            trade_profit = 0
            for trade in executed_trades:
                if state.timestamp > trade.timestamp:  # Skip old trades
                    continue
                    
                if trade.buyer == state.trader_id:
                    # We bought, record negative cash flow
                    trade_profit -= trade.price * trade.quantity
                else:
                    # We sold, record positive cash flow
                    trade_profit += trade.price * trade.quantity
                    
            # Record trade profit
            if trade_profit != 0:
                trader_data["profit_per_product"][product].append(trade_profit)
                # Keep only recent history
                trader_data["profit_per_product"][product] = trader_data["profit_per_product"][product][-20:]
            
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # Skip if insufficient orders
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
            
            # Keep only the last 150 prices (extended history)
            trader_data["price_history"][product] = trader_data["price_history"][product][-150:]
            
            # Get product-specific parameters
            params = self.get_product_params(product)
            alpha = params["alpha"]
            
            # Update EMA
            if product not in trader_data["ema_prices"]:
                trader_data["ema_prices"][product] = mid_price
            else:
                old_ema = trader_data["ema_prices"][product]
                # Adaptive alpha based on trend strength
                adaptive_alpha = alpha
                if len(trader_data["price_history"][product]) > 10:
                    recent_trend = (trader_data["price_history"][product][-1] - 
                                  trader_data["price_history"][product][-5]) / trader_data["price_history"][product][-5]
                    if abs(recent_trend) > 0.01:  # 1% move
                        # Make EMA more responsive during strong trends
                        adaptive_alpha = min(0.5, alpha * (1 + abs(recent_trend) * 5))
                
                new_ema = adaptive_alpha * mid_price + (1 - adaptive_alpha) * old_ema
                trader_data["ema_prices"][product] = new_ema
                
            ema_price = trader_data["ema_prices"][product]
            
            # Calculate volatility with exponential weighting
            volatility = self.calculate_volatility(
                trader_data["price_history"][product], 
                params.get("volatility_window", 8)
            )
            trader_data["volatility"][product] = volatility
            
            # Detect market conditions with enhanced algorithms
            trend_direction, trend_strength = self.detect_trend(
                trader_data["price_history"][product], product
            )
            
            pattern_direction, pattern_confidence = self.detect_pattern(
            trader_data["price_history"][product], product
                        )
            
            # Dynamic spread adjustment
            dynamic_spread = self.dynamic_spread_adjustment(
                product, volatility, trend_direction, 
                mid_price, ema_price
            )
            
            # Calculate optimal price levels based on all analyzed factors
            buy_price, sell_price = self.dynamic_price_levels(
                mid_price, ema_price, dynamic_spread, 
                product, trend_direction, pattern_direction
            )
            
            # Calculate base volume, will be adjusted based on market conditions
            base_volume = 10  # Default base volume
            
            # Get volume available at best prices for volume estimations
            best_bid_volume = abs(order_depth.buy_orders.get(best_bid, 0))
            best_ask_volume = order_depth.sell_orders.get(best_ask, 0)
            market_vol_estimate = (best_bid_volume + best_ask_volume) / 2
            
            # Adjust base volume based on market volume
            base_volume = max(5, min(15, market_vol_estimate * 0.4))
            
            # Sophisticated volume adjustment
            buy_volume = self.adjust_volume(
                base_volume, product, current_position, 
                trend_direction, trend_strength, 
                pattern_direction, pattern_confidence, 
                volatility, trader_data["profit_per_product"].get(product, [])
            )
            
            sell_volume = self.adjust_volume(
                base_volume, product, current_position, 
                -trend_direction, trend_strength, 
                -pattern_direction, pattern_confidence, 
                volatility, trader_data["profit_per_product"].get(product, [])
            )
            
            # Adjust volumes based on position limits
            remaining_buy_capacity = position_limit - current_position
            remaining_sell_capacity = position_limit + current_position
            
            buy_volume = min(buy_volume, remaining_buy_capacity)
            sell_volume = min(sell_volume, remaining_sell_capacity)
            
            # Add main market making orders if capacities allow
            if buy_volume > 0:
                orders.append(Order(product, buy_price, buy_volume))
            
            if sell_volume > 0:
                orders.append(Order(product, sell_price, -sell_volume))
                
            # Add opportunistic orders for significant price dislocations
            opp_orders = self.opportunistic_orders(
                product, order_depth, current_position, 
                position_limit, ema_price
            )
            orders.extend(opp_orders)
            
            # Advanced: Add layered orders at deeper levels
            if remaining_buy_capacity > buy_volume + 5:
                # Add a smaller order at a lower price level
                deep_buy_price = buy_price - max(2, math.floor(dynamic_spread * 0.8))
                deep_buy_volume = math.floor(buy_volume * 0.6)
                if deep_buy_volume > 0:
                    orders.append(Order(product, deep_buy_price, deep_buy_volume))
            
            if remaining_sell_capacity > sell_volume + 5:
                # Add a smaller order at a higher price level
                deep_sell_price = sell_price + max(2, math.floor(dynamic_spread * 0.8))
                deep_sell_volume = math.floor(sell_volume * 0.6)
                if deep_sell_volume > 0:
                    orders.append(Order(product, deep_sell_price, -deep_sell_volume))
            
            # Advanced: Add market taking orders when strong signals detected
            if current_position < position_limit * 0.7 and trend_direction > 0 and pattern_direction > 0:
                # Strong buy signal - consider taking liquidity from the market
                signal_strength = (trend_strength + pattern_confidence) / 2
                if signal_strength > 0.7:
                    market_buy_volume = math.floor(min(5, remaining_buy_capacity * 0.15))
                    if market_buy_volume > 0:
                        orders.append(Order(product, best_ask, market_buy_volume))
            
            if current_position > -position_limit * 0.7 and trend_direction < 0 and pattern_direction < 0:
                # Strong sell signal - consider taking liquidity from the market
                signal_strength = (trend_strength + pattern_confidence) / 2
                if signal_strength > 0.7:
                    market_sell_volume = math.floor(min(5, remaining_sell_capacity * 0.15))
                    if market_sell_volume > 0:
                        orders.append(Order(product, best_bid, -market_sell_volume))
            
            # Record trade info for analytics
            if product not in trader_data["trade_history"]:
                trader_data["trade_history"][product] = []
            
            trader_data["trade_history"][product].append({
                "timestamp": state.timestamp,
                "mid_price": mid_price,
                "ema_price": ema_price,
                "position": current_position,
                "volatility": volatility,
                "trend": trend_direction,
                "pattern": pattern_direction,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "spread": dynamic_spread
            })
            
            # Keep only recent history
            trader_data["trade_history"][product] = trader_data["trade_history"][product][-200:]
            
            # Update result
            result[product] = orders
        
        # Add risk management function
        self.risk_management(trader_data, state)
        
        conversions = 0 # Set default conversion value if none calculated
        return result,conversions, json.dumps(trader_data)
    
    def risk_management(self, trader_data, state: TradingState):
        """
        Advanced risk management function to analyze and adjust trading behavior.
        """
        # For each product, check if we need to adjust parameters
        for product in trader_data.get("trade_history", {}):
            # Skip if not enough history
            if len(trader_data["trade_history"][product]) < 10:
                continue
                
            # Get recent trade history
            recent_trades = trader_data["trade_history"][product][-10:]
            
            # Check for adverse price movements against position
            current_position = state.position.get(product, 0)
            if abs(current_position) > 10:  # Only care if we have significant position
                price_direction = recent_trades[-1]["mid_price"] - recent_trades[-5]["mid_price"]
                
                # Position going against price movement
                if (current_position > 0 and price_direction < 0) or (current_position < 0 and price_direction > 0):
                    # Check severity of the move
                    price_change_pct = abs(price_direction / recent_trades[-5]["mid_price"])
                    
                    if price_change_pct > 0.015:  # 1.5% adverse move
                        # Record this event for future reference
                        if "risk_events" not in trader_data:
                            trader_data["risk_events"] = {}
                        if product not in trader_data["risk_events"]:
                            trader_data["risk_events"][product] = []
                            
                        trader_data["risk_events"][product].append({
                            "timestamp": state.timestamp,
                            "position": current_position,
                            "price_change": price_direction,
                            "severity": price_change_pct
                        })
                        
                        # If we've seen multiple risk events, adjust product parameters
                        if len(trader_data["risk_events"][product]) >= 3:
                            # Make trading more conservative
                            if product in self.PRODUCT_PARAMS:
                                # Reduce position limit temporarily
                                self.PRODUCT_PARAMS[product]["max_position_ratio"] *= 0.85
                                # Increase spread to reduce trading frequency
                                self.PRODUCT_PARAMS[product]["spread"] *= 1.2
                                # Reset risk events
                                trader_data["risk_events"][product] = []
            
            # Check for volatility spikes
            recent_volatility = trader_data.get("volatility", {}).get(product, 0)
            if "volatility_history" not in trader_data:
                trader_data["volatility_history"] = {}
            if product not in trader_data["volatility_history"]:
                trader_data["volatility_history"][product] = []
                
            trader_data["volatility_history"][product].append(recent_volatility)
            trader_data["volatility_history"][product] = trader_data["volatility_history"][product][-20:]
            
            # Check if current volatility is significantly higher than average
            if len(trader_data["volatility_history"][product]) >= 10:
                avg_volatility = sum(trader_data["volatility_history"][product][:-1]) / (len(trader_data["volatility_history"][product]) - 1)
                if recent_volatility > avg_volatility * 2:
                    # Volatility spike detected - reduce trading volume
                    if product in self.PRODUCT_PARAMS:
                        self.PRODUCT_PARAMS[product]["volume_scale"] *= 0.8
                        # Remember to reset this after some time
                        if "vol_adjust_time" not in trader_data:
                            trader_data["vol_adjust_time"] = {}
                        trader_data["vol_adjust_time"][product] = state.timestamp
            
            # Reset volatility adjustments after some time
            if "vol_adjust_time" in trader_data and product in trader_data["vol_adjust_time"]:
                if state.timestamp - trader_data["vol_adjust_time"][product] > 1000:  # 1000 timestamp units
                    if product in self.PRODUCT_PARAMS:
                        # Reset parameters gradually
                        self.PRODUCT_PARAMS[product]["volume_scale"] = min(
                            self.PRODUCT_PARAMS[product]["volume_scale"] * 1.1,
                            self.PRODUCT_PARAMS.get(product, {}).get("original_volume_scale", 1.0)
                        )
                        
            # Profit/Loss analysis for strategy tuning
            if product in trader_data.get("profit_per_product", {}):
                profits = trader_data["profit_per_product"][product]
                if len(profits) >= 10:
                    recent_profit = sum(profits[-5:])
                    older_profit = sum(profits[-10:-5])
                    
                    # Check if performance is declining
                    if recent_profit < older_profit * 0.7 and recent_profit < 0:
                        # Strategy performance degrading - adjust parameters
                        if product in self.PRODUCT_PARAMS:
                            # Reduce alpha to track price changes less aggressively
                            self.PRODUCT_PARAMS[product]["alpha"] *= 0.9
                            # Increase spread for more conservative trading
                            self.PRODUCT_PARAMS[product]["spread"] = min(
                                self.PRODUCT_PARAMS[product]["spread"] * 1.1,
                                self.PRODUCT_PARAMS[product].get("base_spread", 2) * 1.5
                            )
                    # Check if performance is improving
                    elif recent_profit > older_profit * 1.3 and recent_profit > 0:
                        # Strategy performing well - gradually reset parameters
                        if product in self.PRODUCT_PARAMS:
                            # Move alpha back toward original value
                            original_alpha = self.PRODUCT_PARAMS.get(product, {}).get("original_alpha", 0.2)
                            self.PRODUCT_PARAMS[product]["alpha"] = 0.95 * self.PRODUCT_PARAMS[product]["alpha"] + 0.05 * original_alpha
                            # Reduce spread slightly for more aggressive trading
                            original_spread = self.PRODUCT_PARAMS.get(product, {}).get("original_spread", 2)
                            self.PRODUCT_PARAMS[product]["spread"] = 0.95 * self.PRODUCT_PARAMS[product]["spread"] + 0.05 * original_spread
            
    def analyze_market_regime(self, price_history, product):
        """
        Analyze the market regime (ranging, trending, volatile) to adjust strategy.
        
        Args:
            price_history: List of historical prices
            product: Product identifier
            
        Returns:
            regime_type: String indicating market regime
            confidence: Confidence level in the regime classification
        """
        if len(price_history) < 20:
            return "unknown", 0.0
            
        # Calculate different indicators
        volatility = self.calculate_volatility(price_history, 10)
        trend_dir, trend_strength = self.detect_trend(price_history, product)
        
        # Calculate price range as percentage of average price
        recent_prices = price_history[-20:]
        price_range = (max(recent_prices) - min(recent_prices)) / (sum(recent_prices) / len(recent_prices))
        
        # Calculate directional movement
        start_price = recent_prices[0]
        end_price = recent_prices[-1]
        directional_move = abs(end_price - start_price) / start_price
        
        # Calculate oscillation - how much price moves back and forth
        oscillation = 0
        direction_changes = 0
        
        for i in range(1, len(recent_prices)):
            if (recent_prices[i] > recent_prices[i-1] and recent_prices[i-1] <= recent_prices[i-2 if i >= 2 else i-1]) or \
               (recent_prices[i] < recent_prices[i-1] and recent_prices[i-1] >= recent_prices[i-2 if i >= 2 else i-1]):
                direction_changes += 1
                
        oscillation = direction_changes / (len(recent_prices) - 1)
        
        # Classify regime
        if volatility > 4.0 and price_range > 0.08:
            regime = "volatile"
            confidence = min(1.0, (volatility / 4.0) * (price_range / 0.08) * 0.5)
        elif abs(trend_strength) > 0.7 and directional_move > 0.04:
            regime = "trending"
            confidence = min(1.0, (abs(trend_strength) / 0.7) * (directional_move / 0.04) * 0.5)
        elif oscillation > 0.4 and price_range < 0.05:
            regime = "ranging"
            confidence = min(1.0, (oscillation / 0.4) * (0.05 / max(0.01, price_range)) * 0.5)
        else:
            # Mixed or transitioning regime
            regime = "mixed"
            confidence = 0.5
            
        return regime, confidence
        
    def adapt_to_regime(self, product, regime, confidence):
        """
        Adapt trading parameters based on detected market regime
        
        Args:
            product: Product identifier
            regime: Detected market regime type
            confidence: Confidence in the regime detection
        """
        if confidence < 0.6:
            return  # Don't adapt if not confident in regime detection
            
        if product not in self.PRODUCT_PARAMS:
            return
            
        params = self.PRODUCT_PARAMS[product]
        
        # Store original parameters if not already stored
        if "original_alpha" not in params:
            params["original_alpha"] = params["alpha"]
        if "original_spread" not in params:
            params["original_spread"] = params.get("spread", params.get("base_spread", 2))
        if "original_volume_scale" not in params:
            params["original_volume_scale"] = params["volume_scale"]
            
        # Adapt parameters based on regime
        if regime == "volatile":
            # In volatile markets: widen spreads, reduce volume, increase responsiveness
            self.PRODUCT_PARAMS[product]["alpha"] = params["original_alpha"] * 1.3
            self.PRODUCT_PARAMS[product]["spread"] = params["original_spread"] * 1.5
            self.PRODUCT_PARAMS[product]["volume_scale"] = params["original_volume_scale"] * 0.7
            self.PRODUCT_PARAMS[product]["max_position_ratio"] = 0.7
            
        elif regime == "trending":
            # In trending markets: tighten spreads, increase volume, reduce responsiveness
            self.PRODUCT_PARAMS[product]["alpha"] = params["original_alpha"] * 0.9
            self.PRODUCT_PARAMS[product]["spread"] = params["original_spread"] * 0.8
            self.PRODUCT_PARAMS[product]["volume_scale"] = params["original_volume_scale"] * 1.2
            self.PRODUCT_PARAMS[product]["max_position_ratio"] = 0.95
            
        elif regime == "ranging":
            # In ranging markets: optimal for market making
            self.PRODUCT_PARAMS[product]["alpha"] = params["original_alpha"] * 1
            self.PRODUCT_PARAMS[product]["spread"] = params["original_spread"] * 0.9
            self.PRODUCT_PARAMS[product]["volume_scale"] = params["original_volume_scale"] * 1.1
            self.PRODUCT_PARAMS[product]["max_position_ratio"] = 0.85
            
        elif regime == "mixed":
            # In mixed/uncertain markets: return to original parameters
            self.PRODUCT_PARAMS[product]["alpha"] = params["original_alpha"]
            self.PRODUCT_PARAMS[product]["spread"] = params["original_spread"]
            self.PRODUCT_PARAMS[product]["volume_scale"] = params["original_volume_scale"]
            self.PRODUCT_PARAMS[product]["max_position_ratio"] = 0.8