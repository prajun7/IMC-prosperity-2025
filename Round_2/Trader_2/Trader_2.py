from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math
import statistics
import random

class Trader:
    # Position limits for each product
    POSITION_LIMITS = {
        "PICNIC_BASKET1": 60,
        "PICNIC_BASKET2": 100,
        "CROISSANT": 250,
        "JAM": 350,
        "DJEMBE": 60,
        "DEFAULT": 20
    }
    
    # Basket compositions for arbitrage
    BASKET_COMPOSITION = {
        "PICNIC_BASKET1": {
            "CROISSANT": 6,
            "JAM": 3,
            "DJEMBE": 1
        },
        "PICNIC_BASKET2": {
            "CROISSANT": 4,
            "JAM": 2,
            "DJEMBE": 0
        }
    }
    
    # Product-specific parameters based on observed behaviors
    PRODUCT_PARAMS = {
        "PICNIC_BASKET1": {
            "alpha": 0.3,           # EMA weight (increased from 0.25 for faster response)
            "spread_factor": 0.5,   # Reduced spread for more competitive pricing
            "trend_factor": 0.5,    # Increased trend following
            "mean_reversion": True, # Apply mean reversion
            "volatility_scale": 1.3, # Slightly increased volatility scaling
            "min_spread": 2,         # Minimum spread to maintain
            "take_width": 2,         # Reduced distance from mid price to take orders (more aggressive)
            "aggressive_edge": 0.5,  # Increased aggression
            "risk_aversion": 0.3,    # Reduced risk aversion
            "max_position_scale": 1.0, # Full position utilization
        },
        "PICNIC_BASKET2": {
            "alpha": 0.3,
            "spread_factor": 0.5,
            "trend_factor": 0.5,
            "mean_reversion": True,
            "volatility_scale": 1.3,
            "min_spread": 2,
            "take_width": 2,
            "aggressive_edge": 0.5,
            "risk_aversion": 0.3,
            "max_position_scale": 1.0,
        },
        "DJEMBE": {
            "alpha": 0.4,            # Increased from 0.35 for faster response
            "spread_factor": 0.7,    # Slightly reduced for more trades
            "trend_factor": 0.8,     # Increased trend following
            "mean_reversion": False, # No mean reversion - follows trends
            "volatility_scale": 1.6,  # Slightly reduced volatility scaling
            "min_spread": 2,         # Reduced minimum spread
            "take_width": 3,         # Reduced distance from mid price to take orders
            "aggressive_edge": 0.7,  # More aggressive
            "risk_aversion": 0.5,    # Reduced risk aversion
            "max_position_scale": 0.9, # Increased max position
        },
        "CROISSANT": {
            "alpha": 0.35,           # Increased from 0.3
            "spread_factor": 0.6,    # Reduced spread
            "trend_factor": 0.6,     # Increased trend following
            "mean_reversion": True,  # Apply mean reversion
            "volatility_scale": 1.3, # Reduced volatility scaling
            "min_spread": 1,         # Reduced minimum spread
            "take_width": 2,         # Reduced distance for more aggressive order taking
            "aggressive_edge": 0.6,  # Increased aggression
            "risk_aversion": 0.4,    # Reduced risk aversion
            "max_position_scale": 1.0, # Full position utilization
        },
        "JAM": {
            "alpha": 0.35,           # Increased from 0.3
            "spread_factor": 0.6,    # Reduced spread
            "trend_factor": 0.7,     # Increased trend following
            "mean_reversion": True,  # Apply mean reversion
            "volatility_scale": 1.4, # Slightly reduced volatility scaling
            "min_spread": 1,         # Reduced minimum spread
            "take_width": 2,         # Reduced distance for more aggressive order taking
            "aggressive_edge": 0.6,  # Increased aggression
            "risk_aversion": 0.4,    # Reduced risk aversion
            "max_position_scale": 1.0, # Full position utilization
        }
    }
    
    # Default parameters for any new product
    DEFAULT_PARAMS = {
        "alpha": 0.35,           # Increased from 0.3
        "spread_factor": 0.6,    # Reduced spread
        "trend_factor": 0.6,     # Increased trend following
        "mean_reversion": True,  # Default to mean reversion
        "volatility_scale": 1.2, # Increased volatility scale
        "min_spread": 1,         # Reduced minimum spread
        "take_width": 2,         # Reduced take width for more aggressive order taking
        "aggressive_edge": 0.6,  # Increased aggression
        "risk_aversion": 0.4,    # Reduced risk aversion
        "max_position_scale": 1.0, # Full position utilization
    }
    
    # Arbitrage parameters
    ARBITRAGE_PARAMS = {
        "min_profit_per_lot": 1,     # Minimum profit required per lot to execute arbitrage
        "max_arbitrage_lots": 10,    # Maximum number of lots to arbitrage at once
        "aggressive_factor": 1.0,    # Factor to determine how aggressively to execute arbitrage
        "basket_discount": 0.97,     # Expected basket discount compared to components (3%)
    }
    
    # Drawdown protection parameters with more generous recovery
    DRAWDOWN_PROTECTION = {
        "window_size": 8,        # Reduced window to detect drawdown faster
        "threshold": 0.04,       # Reduced threshold to 4%
        "reduction_factor": 0.6, # Less severe reduction (from 0.5)
        "recovery_factor": 0.3,  # Increased recovery factor (from 0.2)
    }
    
    def __init__(self):
        """Initialize the trader with empty state variables."""
        self.price_history = {}   # Store price history for all products
        self.volatility = {}      # Store volatility estimates for products
        self.ema_prices = {}      # Store EMA prices
        self.last_mid_prices = {} # Last observed mid prices
        self.position_history = {} # Historical positions
        self.market_trend = {}    # Market trend indicators
        self.pnl_history = {}     # Historical PnL for drawdown detection
        self.market_regime = {}   # Current market regime (normal, volatile, etc.)
        self.success_rate = {}    # Success rate of recent trades
        self.fair_values = {}     # Track fair values across products
        self.arbitrage_executed = {} # Track arbitrage opportunities executed
        
    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])
        
    def get_product_params(self, product):
        """Get parameters for a specific product, or use defaults."""
        return self.PRODUCT_PARAMS.get(product, self.DEFAULT_PARAMS)
    
    def detect_market_regime(self, product, trader_data, current_price):
        """Detect the current market regime with improved sensitivity."""
        # Initialize needed structures
        if "market_regime" not in trader_data:
            trader_data["market_regime"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        
        # If we don't have enough history, assume normal regime
        if product not in trader_data["price_history"] or len(trader_data["price_history"].get(product, [])) < 5:
            trader_data["market_regime"][product] = "normal"
            return "normal", trader_data
            
        # Get recent price history
        prices = trader_data["price_history"][product][-8:]  # Use more history for better detection
        
        # Calculate various regime indicators
        
        # 1. Consecutive moves in same direction (trending indicator)
        consecutive_up = 0
        consecutive_down = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                consecutive_up += 1
                consecutive_down = 0
            elif prices[i] < prices[i-1]:
                consecutive_down += 1
                consecutive_up = 0
        
        # 2. Volatility indicator
        recent_volatility = trader_data["volatility"].get(product, 0.01)
        
        # 3. Mean reversion indicator - distance from moving average
        avg_price = sum(prices) / len(prices)
        price_deviation = abs(current_price - avg_price) / avg_price
        
        # 4. Trend strength indicator
        trend_strength = abs(prices[-1] - prices[0]) / (max(prices) - min(prices) + 0.001)
        
        # Determine regime based on indicators
        if (consecutive_up >= 3 or consecutive_down >= 3) and trend_strength > 0.5:
            regime = "trending"
        elif recent_volatility > 0.025:  # Reduced threshold for volatile detection
            regime = "volatile"
        elif price_deviation > 0.015:    # Reduced threshold for mean reversion detection
            regime = "mean_reverting"
        else:
            regime = "normal"
            
        # Update regime with some hysteresis to prevent rapid switching
        old_regime = trader_data["market_regime"].get(product, "normal")
        if old_regime != regime:
            # Less strict regime switching
            if (regime == "volatile" and recent_volatility > 0.035) or \
               (regime == "trending" and (consecutive_up >= 3 or consecutive_down >= 3)) or \
               (regime == "mean_reverting" and price_deviation > 0.025):
                trader_data["market_regime"][product] = regime
            else:
                # Otherwise stay with the current regime
                regime = old_regime
        
        return regime, trader_data
    
    def calculate_volatility(self, product, mid_price, trader_data):
        """Calculate and update volatility for a product."""
        history_len = 20  # Increased history length for better volatility estimate
        
        # Initialize needed structures
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        
        # Initialize price history if needed
        if product not in trader_data["price_history"]:
            trader_data["price_history"][product] = []
        
        # Add current price to history
        trader_data["price_history"][product].append(mid_price)
        
        # Keep only the most recent prices
        if len(trader_data["price_history"][product]) > history_len:
            trader_data["price_history"][product] = trader_data["price_history"][product][-history_len:]
        
        # Calculate volatility if we have enough data points
        if len(trader_data["price_history"][product]) >= 3:
            # Calculate price changes as percentage
            price_changes = [
                abs((trader_data["price_history"][product][i] / trader_data["price_history"][product][i-1]) - 1) 
                for i in range(1, len(trader_data["price_history"][product]))
            ]
            
            # Volatility as standard deviation of price changes
            if len(price_changes) > 0:
                volatility = statistics.stdev(price_changes) if len(price_changes) > 1 else price_changes[0]
                
                # Update volatility using exponential smoothing
                old_volatility = trader_data["volatility"].get(product, volatility)
                trader_data["volatility"][product] = 0.8 * old_volatility + 0.2 * volatility
                
                return trader_data["volatility"][product]
        
        # Default low volatility if we can't calculate it
        if product not in trader_data["volatility"]:
            trader_data["volatility"][product] = 0.01
            
        return trader_data["volatility"][product]
    
    def calculate_trend(self, product, mid_price, trader_data):
        """Calculate market trend for a product with improved smoothing."""
        # Initialize needed structures
        if "last_mid_prices" not in trader_data:
            trader_data["last_mid_prices"] = {}
        if "market_trend" not in trader_data:
            trader_data["market_trend"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
            
        last_mid = trader_data["last_mid_prices"].get(product, mid_price)
        
        # Get trend based on price history if available
        if product in trader_data["price_history"] and len(trader_data["price_history"][product]) >= 6:
            prices = trader_data["price_history"][product]
            
            # Calculate multiple moving averages for better trend detection
            short_ma = sum(prices[-3:]) / 3
            med_ma = sum(prices[-6:]) / 6
            long_ma = sum(prices) / len(prices)
            
            # Use weighted moving average crossovers for trend signal
            if short_ma > med_ma and med_ma > long_ma:
                current_trend = 1.5  # Strong uptrend
            elif short_ma > med_ma:
                current_trend = 1.0  # Moderate uptrend
            elif short_ma < med_ma and med_ma < long_ma:
                current_trend = -1.5  # Strong downtrend
            elif short_ma < med_ma:
                current_trend = -1.0  # Moderate downtrend
            else:
                current_trend = 0  # No clear trend
                
            # Add momentum indicator - recent price change
            if len(prices) >= 4:
                recent_change = (prices[-1] - prices[-4]) / prices[-4]
                momentum = 0.5 * (1 if recent_change > 0 else -1 if recent_change < 0 else 0)
                current_trend += momentum
        else:
            # Simple trend based on last price movement with magnitude
            price_change_pct = (mid_price - last_mid) / last_mid if last_mid != 0 else 0
            if price_change_pct > 0.005:  # Significant up move
                current_trend = 1.5
            elif price_change_pct > 0:     # Small up move
                current_trend = 1
            elif price_change_pct < -0.005: # Significant down move
                current_trend = -1.5
            elif price_change_pct < 0:      # Small down move
                current_trend = -1
            else:
                current_trend = 0
                
        # Update the trend with exponential smoothing
        old_trend = trader_data["market_trend"].get(product, 0)
        trader_data["market_trend"][product] = 0.7 * old_trend + 0.3 * current_trend
        
        # Update last mid price
        trader_data["last_mid_prices"][product] = mid_price
        
        return trader_data["market_trend"][product]
    
    def detect_drawdown(self, product, trader_data, position, mid_price):
        """Detect if we're in a drawdown period with improved recovery."""
        position_limit = self.get_position_limit(product)
        
        # Initialize all required structures
        if "pnl_history" not in trader_data:
            trader_data["pnl_history"] = {}
        if "position_history" not in trader_data:
            trader_data["position_history"] = {}
        if "in_drawdown" not in trader_data:
            trader_data["in_drawdown"] = {}
        if "last_mid_prices" not in trader_data:
            trader_data["last_mid_prices"] = {}
        if "drawdown_counter" not in trader_data:
            trader_data["drawdown_counter"] = {}
            
        if product not in trader_data["pnl_history"]:
            trader_data["pnl_history"][product] = []
        if product not in trader_data["position_history"]:
            trader_data["position_history"][product] = []
        if product not in trader_data["in_drawdown"]:
            trader_data["in_drawdown"][product] = False
        if product not in trader_data["drawdown_counter"]:
            trader_data["drawdown_counter"][product] = 0
            
        # Estimate current PnL
        last_position = trader_data["position_history"][product][-1] if trader_data["position_history"][product] else 0
        last_price = trader_data["last_mid_prices"].get(product, mid_price)
        
        # Simple PnL estimation based on position change and price change
        if last_position != position:
            # If position changed, record the result
            position_change = position - last_position
            price_change = mid_price - last_price
            trade_pnl = position_change * price_change
            
            # Record this PnL and maintain max length
            trader_data["pnl_history"][product].append(trade_pnl)
            if len(trader_data["pnl_history"][product]) > self.DRAWDOWN_PROTECTION["window_size"]:
                trader_data["pnl_history"][product] = trader_data["pnl_history"][product][-self.DRAWDOWN_PROTECTION["window_size"]:]
            
        # Update position history
        trader_data["position_history"][product].append(position)
        if len(trader_data["position_history"][product]) > 25:  # Keep more position history
            trader_data["position_history"][product] = trader_data["position_history"][product][-25:]
            
        # Check if we're in a drawdown
        if len(trader_data["pnl_history"][product]) >= self.DRAWDOWN_PROTECTION["window_size"]:
            recent_pnl = trader_data["pnl_history"][product]
            cumulative_pnl = sum(recent_pnl)
            
            # If cumulative PnL is negative beyond threshold, trigger drawdown protection
            if cumulative_pnl < -self.DRAWDOWN_PROTECTION["threshold"] * position_limit:
                trader_data["in_drawdown"][product] = True
                trader_data["drawdown_counter"][product] = 0  # Reset counter
            # If we're in a drawdown and see positive PnL, gradually recover
            elif trader_data["in_drawdown"][product]:
                # Increment recovery counter
                trader_data["drawdown_counter"][product] += 1
                
                # Exit drawdown if we've had a sustained recovery or enough time has passed
                if cumulative_pnl > 0 or trader_data["drawdown_counter"][product] >= 10:
                    recovery_chance = self.DRAWDOWN_PROTECTION["recovery_factor"] * (1 + trader_data["drawdown_counter"][product] / 10)
                    if random.random() < min(recovery_chance, 0.8):  # Cap at 80% chance
                        trader_data["in_drawdown"][product] = False
                        trader_data["drawdown_counter"][product] = 0
        
        return trader_data["in_drawdown"].get(product, False), trader_data
    
    def should_take_order(self, product, price, fair_value, take_width, is_buy, regime, volatility):
        """Determine if we should take an existing order with adaptive thresholds."""
        # Adjust take width based on market regime and volatility
        adjusted_take_width = take_width
        
        if regime == "volatile":
            # More conservative in volatile markets
            adjusted_take_width = take_width * 1.4  # Slightly reduced from 1.5
        elif regime == "trending":
            # More aggressive in trending markets
            adjusted_take_width = take_width * 0.7  # Reduced from 0.8
        elif regime == "mean_reverting":
            # More aggressive in mean reverting markets (opportunity for profit)
            adjusted_take_width = take_width * 0.75
            
        # Add volatility adjustment
        volatility_adjustment = volatility * 80  # Reduced from 100
        adjusted_take_width += volatility_adjustment
        
        # Set minimum and maximum bounds on take width
        adjusted_take_width = max(1, min(adjusted_take_width, take_width * 2))
        
        if is_buy:
            # For buy orders, we take if the price is below fair value - take width
            return price <= fair_value - adjusted_take_width
        else:
            # For sell orders, we take if the price is above fair value + take width
            return price >= fair_value + adjusted_take_width
            
    def take_best_orders(self, product, fair_value, orders, order_depth, position, params, regime, volatility, in_drawdown):
        """Take favorable orders from the market with improved selectivity."""
        take_width = params["take_width"]
        position_limit = self.get_position_limit(product)
        
        # Adjust position limit if in drawdown
        effective_limit = position_limit
        if in_drawdown:
            effective_limit = math.floor(position_limit * self.DRAWDOWN_PROTECTION["reduction_factor"])
            
        # Further adjust by the product's max position scale parameter
        effective_limit = math.floor(effective_limit * params["max_position_scale"])
        
        buy_order_volume = 0
        sell_order_volume = 0
        
        # Check for profitable sell orders (we buy)
        if len(order_depth.sell_orders) != 0:
            # Sort sell orders by price, cheapest first
            sell_prices = sorted(order_depth.sell_orders.keys())
            
            for price in sell_prices:
                amount = abs(order_depth.sell_orders[price])
                
                # Check if this order is worth taking
                if self.should_take_order(product, price, fair_value, take_width, True, regime, volatility):
                    # Calculate how much we can buy based on position limits
                    max_buy = effective_limit - position - buy_order_volume
                    quantity = min(amount, max_buy)
                    
                    if quantity > 0:
                        orders.append(Order(product, price, quantity))
                        buy_order_volume += quantity
                        
                        # If we're fully invested, stop looking at more orders
                        if buy_order_volume >= max_buy:
                            break
                else:
                    # If this order isn't worth taking, later ones at higher prices won't be either
                    break
        
        # Check for profitable buy orders (we sell)
        if len(order_depth.buy_orders) != 0:
            # Sort buy orders by price, highest first
            buy_prices = sorted(order_depth.buy_orders.keys(), reverse=True)
            
            for price in buy_prices:
                amount = order_depth.buy_orders[price]
                
                # Check if this order is worth taking
                if self.should_take_order(product, price, fair_value, take_width, False, regime, volatility):
                    # Calculate how much we can sell based on position limits
                    max_sell = effective_limit + position - sell_order_volume
                    quantity = min(amount, max_sell)
                    
                    if quantity > 0:
                        orders.append(Order(product, price, -quantity))
                        sell_order_volume += quantity
                        
                        # If we've reached our sell limit, stop looking at more orders
                        if sell_order_volume >= max_sell:
                            break
                else:
                    # If this order isn't worth taking, later ones at lower prices won't be either
                    break
                    
        return orders, buy_order_volume, sell_order_volume
    
    def calculate_fair_value(self, product, mid_price, trader_data, params, regime):
        """Calculate the fair value with improved signal processing."""
        alpha = params["alpha"]
        trend_factor = params["trend_factor"]
        
        # Initialize needed structures
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "fair_values" not in trader_data:
            trader_data["fair_values"] = {}
        
        # Adjust alpha based on regime
        if regime == "volatile":
            # Use faster-moving average in volatile markets
            alpha = min(0.7, alpha * 1.5)
        elif regime == "trending":
            # Use faster-moving average in trending markets
            alpha = min(0.6, alpha * 1.3)
        elif regime == "mean_reverting":
            # Use slower-moving average in mean-reverting markets
            alpha = max(0.15, alpha * 0.7)
        
        # Initialize EMA price if not exists
        if product not in trader_data["ema_prices"]:
            trader_data["ema_prices"][product] = mid_price
            fair_value = mid_price
        else:
            # Calculate EMA
            old_ema = trader_data["ema_prices"][product]
            new_ema = alpha * mid_price + (1 - alpha) * old_ema
            trader_data["ema_prices"][product] = new_ema
            
            # Calculate trend adjustment
            trend = self.calculate_trend(product, mid_price, trader_data)
            
            # Adjust trend factor based on regime
            regime_trend_factor = trend_factor
            if regime == "trending":
                # Increase trend following in trending markets
                regime_trend_factor = trend_factor * 1.7  # Increased from 1.5
            elif regime == "mean_reverting":
                # Decrease trend following in mean-reverting markets
                regime_trend_factor = trend_factor * 0.4  # Decreased from 0.5
            
            # Apply trend factor to fair value calculation
            trend_adjustment = trend * regime_trend_factor * trader_data["volatility"].get(product, 0.01) * mid_price
            
            if params["mean_reversion"] and regime != "trending":
                # For mean reverting products, move against the trend
                fair_value = new_ema - trend_adjustment
            else:
                # For trend following products, enhance the trend
                fair_value = new_ema + trend_adjustment
        
        # Store fair value for use in arbitrage calculations
        trader_data["fair_values"][product] = fair_value
                
        return fair_value, trader_data
        
    def calculate_spread(self, product, fair_value, trader_data, params, regime, in_drawdown):
        """Calculate appropriate bid-ask spread based on market conditions."""
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
            
        volatility = trader_data["volatility"].get(product, 0.01)
        spread_factor = params["spread_factor"]
        min_spread = params["min_spread"]
        
        # Adjust spread factor based on market regime
        if regime == "volatile":
            spread_factor *= 1.4  # Reduced from 1.5
            min_spread = max(min_spread + 1, min_spread * 1.4)
        elif regime == "trending":
            spread_factor *= 0.8  # Reduced from 0.9 for tighter spreads
            min_spread = max(1, min_spread - 1)  # Allow tighter spreads in trending markets
        elif regime == "mean_reverting":
            spread_factor *= 1.1  # Reduced from 1.2
            
        # Further adjust if in drawdown protection mode
        if in_drawdown:
            spread_factor *= 1.3  # Reduced from 1.5
            min_spread = max(min_spread + 1, min_spread * 1.5)
        
        # Calculate base spread as a function of volatility and fair value
        base_spread = max(
            min_spread, 
            math.ceil(volatility * params["volatility_scale"] * fair_value * spread_factor)
        )
        
        # Adjust spread based on our current position
        position = trader_data["current_position"].get(product, 0)
        position_limit = self.get_position_limit(product)
        position_ratio = abs(position) / position_limit if position_limit > 0 else 0
        
        # Risk aversion factor affects how much we widen spread as position grows
        risk_aversion = params["risk_aversion"]
        
        # Use a logarithmic function for position adjustment to be less aggressive
        # for medium positions but more aggressive for positions close to limits
        position_adjustment = math.ceil(math.log(1 + 5 * position_ratio) * base_spread * risk_aversion)
        
        return base_spread + position_adjustment
    
    def make_market(self, product, fair_value, spread, orders, position, trader_data, params, regime, in_drawdown):
        """Place market making orders with dynamic sizing."""
        position_limit = self.get_position_limit(product)
        aggressive_edge = params["aggressive_edge"]
        
        # Adjust position limit if in drawdown
        effective_limit = position_limit
        if in_drawdown:
            effective_limit = math.floor(position_limit * self.DRAWDOWN_PROTECTION["reduction_factor"])
            
        # Further adjust by the product's max position scale parameter
        effective_limit = math.floor(effective_limit * params["max_position_scale"])
        
        # Adjust aggressiveness based on market regime
        if regime == "volatile":
            aggressive_edge *= 0.8  # Less aggressive in volatile markets (up from 0.7)
        elif regime == "trending":
            aggressive_edge *= 1.3  # More aggressive in trending markets (up from 1.2)
        elif regime == "mean_reverting":
            aggressive_edge *= 1.1  # Slightly more aggressive in mean reverting markets
        
        # Calculate appropriate bid and ask prices
        half_spread = spread / 2
        
        # Apply asymmetric spreads based on our position and trend
        trend = trader_data["market_trend"].get(product, 0)
        position_bias = -position / effective_limit if effective_limit > 0 else 0
        
        # Combine trend and position bias for dynamic spread adjustment
        bias_factor = (trend * 0.3) + (position_bias * 0.7)
        bias_adjustment = half_spread * bias_factor * 0.5  # Reduced impact from 0.6
        
        # Calculate bid and ask prices with bias adjustment
        bid_price = math.floor(fair_value - half_spread + bias_adjustment)
        ask_price = math.ceil(fair_value + half_spread + bias_adjustment)
        
        # Ensure spread doesn't get too tight
        if ask_price - bid_price < params["min_spread"]:
            spread_adjustment = (params["min_spread"] - (ask_price - bid_price)) / 2
            bid_price = math.floor(bid_price - spread_adjustment)
            ask_price = math.ceil(ask_price + spread_adjustment)
        
        # Calculate appropriate order sizes
        remaining_buy = effective_limit - position
        remaining_sell = effective_limit + position
        
        # Dynamic sizing based on position, market regime, and drawdown state
        base_size = max(1, int(effective_limit * 0.1))  # Base size at 10% of position limit
        
        # Adjust size based on regime
        if regime == "volatile":
            base_size = max(1, int(base_size * 0.8))  # Reduced size in volatile markets (up from 0.7)
        elif regime == "trending":
            base_size = max(1, int(base_size * 1.3))  # Increased size in trending markets (up from 1.2)
        
        # Further reduce size if in drawdown
        if in_drawdown:
            base_size = max(1, int(base_size * 0.7))  # Reduced from 0.6
            
        # Calculate final sizes with asymmetric sizing based on position
        buy_size = min(remaining_buy, math.ceil(base_size * (1 + aggressive_edge * (1 - position_bias))))
        sell_size = min(remaining_sell, math.ceil(base_size * (1 + aggressive_edge * (1 + position_bias))))
        
        # Place the orders
        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))
            
        return orders
    
    def manage_basket_arbitrage(self, products, inventory, trader_data, order_depths, orders):
        """Look for and execute basket arbitrage opportunities."""
        # Initialize needed data structures
        if "fair_values" not in trader_data:
            trader_data["fair_values"] = {}
        if "arbitrage_executed" not in trader_data:
            trader_data["arbitrage_executed"] = {}
            
        # Check if we have all necessary basket components and basket itself in the market
        for basket_name, composition in self.BASKET_COMPOSITION.items():
            # Skip if basket or any component is not in current products
            if basket_name not in products:
                continue
                
            all_components_available = True
            for component in composition:
                if component not in products:
                    all_components_available = False
                    break
                    
            if not all_components_available:
                continue
                
            # Check for arbitrage opportunities
            basket_position = inventory.get(basket_name, 0)
            basket_position_limit = self.get_position_limit(basket_name)
            
            # Get basket price
            basket_depth = order_depths.get(basket_name, None)
            if not basket_depth:
                continue
                
            # Check component fair values and current positions
            component_value = 0
            component_limits_ok = True
            component_positions = {}
            
            for component, quantity in composition.items():
                component_position = inventory.get(component, 0)
                component_limit = self.get_position_limit(component)
                component_positions[component] = component_position
                
                # Calculate component value using fair value as a reference
                if component in trader_data["fair_values"]:
                    component_value += trader_data["fair_values"][component] * quantity
                else:
                    # If no fair value, use mid price from order book
                    component_depth = order_depths.get(component, None)
                    if not component_depth or not component_depth.buy_orders or not component_depth.sell_orders:
                        component_limits_ok = False
                        break
                        
                    component_mid = (max(component_depth.buy_orders.keys()) + min(component_depth.sell_orders.keys())) / 2
                    component_value += component_mid * quantity
            
            if not component_limits_ok:
                continue
                
            # Apply basket discount - baskets should be cheaper than components
            expected_basket_value = component_value * self.ARBITRAGE_PARAMS["basket_discount"]
            
            # Check both arbitrage directions:
            # 1. Buy basket, sell components
            # 2. Buy components, sell basket
            
            # Initialize tracking for executed arbitrage
            if basket_name not in trader_data["arbitrage_executed"]:
                trader_data["arbitrage_executed"][basket_name] = {
                    "buy_basket_sell_components": 0,
                    "buy_components_sell_basket": 0
                }
            
            # Direction 1: Buy basket, sell components
            if basket_depth.sell_orders:
                # Get best basket ask price
                basket_ask = min(basket_depth.sell_orders.keys())
                basket_ask_volume = abs(basket_depth.sell_orders[basket_ask])
                
                # Calculate profit for this direction
                potential_profit = expected_basket_value - basket_ask
                
                if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                    # Check position limits
                    max_baskets = min(
                        basket_ask_volume,
                        self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                        basket_position_limit - basket_position
                    )
                    
                    # Check component position limits
                    for component, quantity in composition.items():
                        component_position = component_positions[component]
                        component_limit = self.get_position_limit(component)
                        max_component_lots = (component_limit - component_position) // quantity
                        max_baskets = min(max_baskets, max_component_lots)
                    
                    # Execute arbitrage if profitable and within limits
                    if max_baskets > 0:
                        # Buy basket
                        orders.append(Order(basket_name, basket_ask, max_baskets))
                        
                        # Sell components
                        for component, quantity in composition.items():
                            # Find best bid price for component
                            component_depth = order_depths.get(component)
                            if component_depth and component_depth.buy_orders:
                                component_bid = max(component_depth.buy_orders.keys())
                                # Sell the components at market
                                orders.append(Order(component, component_bid, -max_baskets * quantity))
                                
                        # Update tracking
                        trader_data["arbitrage_executed"][basket_name]["buy_basket_sell_components"] += max_baskets
                        
            # Direction 2: Buy components, sell basket
            if basket_depth.buy_orders:
                # Get best basket bid price
                basket_bid = max(basket_depth.buy_orders.keys())
                basket_bid_volume = basket_depth.buy_orders[basket_bid]
                
                # Calculate profit for this direction
                potential_profit = basket_bid - expected_basket_value
                
                if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                    # Check position limits
                    max_baskets = min(
                        basket_bid_volume,
                        self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                        basket_position_limit + basket_position
                    )
                    
                    # Check component position limits
                    for component, quantity in composition.items():
                        component_position = component_positions[component]
                        component_limit = self.get_position_limit(component)
                        max_component_lots = (component_position + component_limit) // quantity
                        max_baskets = min(max_baskets, max_component_lots)
                    
                    # Execute arbitrage if profitable and within limits
                    if max_baskets > 0:
                        # Sell basket
                        orders.append(Order(basket_name, basket_bid, -max_baskets))
                        
                        # Buy components
                        for component, quantity in composition.items():
                            # Find best ask price for component
                            component_depth = order_depths.get(component)
                            if component_depth and component_depth.sell_orders:
                                component_ask = min(component_depth.sell_orders.keys())
                                # Buy the components at market
                                orders.append(Order(component, component_ask, max_baskets * quantity))
                                
                        # Update tracking
                        trader_data["arbitrage_executed"][basket_name]["buy_components_sell_basket"] += max_baskets
        
        return orders, trader_data
    
    def run(self, state: TradingState):
        """Main trading logic implementation."""
        try:
            # Load or initialize trader data
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except (json.JSONDecodeError, TypeError):
            trader_data = {}
            
        result = {}
        
        # Initialize common data structures
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
        
        # Track positions for all products
        for product in state.position:
            trader_data["current_position"][product] = state.position.get(product, 0)
            
        # Look for arbitrage opportunities first
        if len(state.order_depths) > 1:  # Need at least 2 products for arbitrage
            arbitrage_orders = []
            arbitrage_orders, trader_data = self.manage_basket_arbitrage(
                state.order_depths.keys(),
                state.position,
                trader_data,
                state.order_depths,
                arbitrage_orders
            )
            
            # Add arbitrage orders to result by product
            for order in arbitrage_orders:
                if order.symbol not in result:
                    result[order.symbol] = []
                result[order.symbol].append(order)
            
        # Process each product individually
        for product in state.order_depths.keys():
            # Skip products we don't have position information for
            if product not in state.position:
                continue
                
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            
            # Skip empty order books
            if not order_depth.buy_orders and not order_depth.sell_orders:
                continue
                
            # Calculate mid price
            if len(order_depth.sell_orders) > 0 and len(order_depth.buy_orders) > 0:
                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())
                
                if best_bid >= best_ask:  # Check for crossed/invalid book
                    continue
                    
                mid_price = (best_bid + best_ask) / 2
            elif len(order_depth.sell_orders) > 0:
                mid_price = min(order_depth.sell_orders.keys())
            else:
                mid_price = max(order_depth.buy_orders.keys())
                
            # Get product-specific parameters
            params = self.get_product_params(product)
                
            # Calculate volatility
            volatility = self.calculate_volatility(product, mid_price, trader_data)
            
            # Detect market regime
            regime, trader_data = self.detect_market_regime(product, trader_data, mid_price)
            
            # Detect drawdown for position management
            in_drawdown, trader_data = self.detect_drawdown(product, trader_data, position, mid_price)
            
            # Calculate fair value for this product
            fair_value, trader_data = self.calculate_fair_value(product, mid_price, trader_data, params, regime)
            
            # Initialize orders list for this product
            orders = []
            
            # Take favorable orders first (opportunistic trading)
            orders, buy_order_volume, sell_order_volume = self.take_best_orders(
                product, fair_value, orders, order_depth, position, 
                params, regime, volatility, in_drawdown
            )
            
            # Update position for spread calculation after taking orders
            adjusted_position = position + buy_order_volume - sell_order_volume
            trader_data["current_position"][product] = adjusted_position
            
            # Calculate appropriate spread for market making
            spread = self.calculate_spread(product, fair_value, trader_data, params, regime, in_drawdown)
            
            # Add market making orders
            orders = self.make_market(
                product, fair_value, spread, orders, adjusted_position, 
                trader_data, params, regime, in_drawdown
            )
            
            # Only add product to result if we have orders
            if orders:
                result[product] = orders
                
        # Serialize trader data for persistence
        traderData = json.dumps(trader_data)
        
        # No conversions in this implementation
        conversions = 0
        
        return result, conversions, traderData