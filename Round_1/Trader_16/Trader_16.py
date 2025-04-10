from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
import math
import statistics
import random  # For probabilistic recovery from drawdown

class Trader:
    # Position limits for each product
    POSITION_LIMITS = {
        "RAINFOREST_RESIN": 50,
        "KELP": 50,
        "SQUID_INK": 50,
        "DEFAULT": 20
    }
    
    # Product-specific parameters
    PRODUCT_PARAMS = {
        "RAINFOREST_RESIN": {
            "alpha": 0.2,           # EMA weight (low due to stability)
            "spread_factor": 0.5,   # Narrower spread due to stability
            "trend_factor": 0.3,    # Moderate trend following
            "mean_reversion": True, # Apply mean reversion
            "volatility_scale": 1.0, # Standard volatility scaling
            "min_spread": 1,        # Minimum spread to maintain
            "take_width": 2,        # Distance from mid price to take orders
            "aggressive_edge": 0.3,  # Less aggressive due to stability
            "risk_aversion": 0.3,    # Lower risk aversion
            "max_position_scale": 1.0, # Full position utilization
        },
        "KELP": {
            "alpha": 0.3,           # Medium EMA weight
            "spread_factor": 0.7,   # Medium spread
            "trend_factor": 0.7,    # Higher trend following
            "mean_reversion": False, # No mean reversion - follows trends
            "volatility_scale": 1.5, # Higher volatility scaling
            "min_spread": 2,        # Minimum spread
            "take_width": 3,        # Distance from mid price to take orders
            "aggressive_edge": 0.5,  # Medium aggression
            "risk_aversion": 0.5,    # Medium risk aversion
            "max_position_scale": 0.9, # Slightly reduced max position 
        },
        "SQUID_INK": {
            "alpha": 0.4,           # Higher EMA weight due to volatility
            "spread_factor": 1.0,   # Wider spread for volatility
            "trend_factor": 0.8,    # Strong trend following
            "mean_reversion": True, # Apply mean reversion for high volatility
            "volatility_scale": 2.0, # Higher volatility scaling
            "min_spread": 3,        # Higher minimum spread for safety
            "take_width": 4,        # Distance from mid price to take orders
            "aggressive_edge": 0.7,  # More aggressive due to volatility
            "risk_aversion": 0.7,    # Higher risk aversion
            "max_position_scale": 0.8, # Reduced max position for safety
        }
    }
    
    # Default parameters for any new product
    DEFAULT_PARAMS = {
        "alpha": 0.3,           # Default EMA weight
        "spread_factor": 0.8,   # Default spread factor
        "trend_factor": 0.5,    # Default trend factor
        "mean_reversion": True, # Default to mean reversion
        "volatility_scale": 1.0, # Default volatility scale
        "min_spread": 2,        # Default minimum spread
        "take_width": 3,        # Default take width
        "aggressive_edge": 0.5, # Default aggression
        "risk_aversion": 0.5,   # Default risk aversion
        "max_position_scale": 0.9, # Default position scale
    }
    
    # Drawdown protection parameters
    DRAWDOWN_PROTECTION = {
        "window_size": 10,       # Window to detect drawdown
        "threshold": 0.05,       # 5% drawdown threshold to trigger protection
        "reduction_factor": 0.5, # Position size reduction during drawdown
        "recovery_factor": 0.2,  # Recovery factor to gradually increase positions
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
        
    def get_position_limit(self, product):
        """Gets the position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])
        
    def get_product_params(self, product):
        """Get parameters for a specific product, or use defaults."""
        return self.PRODUCT_PARAMS.get(product, self.DEFAULT_PARAMS)
    
    def detect_market_regime(self, product, trader_data, current_price):
        """Detect the current market regime (trending, mean-reverting, volatile)."""
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
        prices = trader_data["price_history"][product][-5:]
        
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
        
        # Determine regime based on indicators
        if consecutive_up >= 3 or consecutive_down >= 3:
            regime = "trending"
        elif recent_volatility > 0.03:  # High volatility threshold
            regime = "volatile"
        elif price_deviation > 0.02:    # Price far from moving average
            regime = "mean_reverting"
        else:
            regime = "normal"
            
        # Update regime with some hysteresis to prevent rapid switching
        old_regime = trader_data["market_regime"].get(product, "normal")
        if old_regime != regime:
            # Only switch regimes if the new regime is strongly indicated
            if (regime == "volatile" and recent_volatility > 0.05) or \
               (regime == "trending" and (consecutive_up >= 4 or consecutive_down >= 4)) or \
               (regime == "mean_reverting" and price_deviation > 0.03):
                trader_data["market_regime"][product] = regime
            else:
                # Otherwise stay with the current regime
                regime = old_regime
        
        return regime, trader_data
    
    def calculate_volatility(self, product, mid_price, trader_data):
        """Calculate and update volatility for a product."""
        history_len = 15  # Increased history length for better volatility estimate
        
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
        """Calculate market trend for a product with better smoothing."""
        # Initialize needed structures
        if "last_mid_prices" not in trader_data:
            trader_data["last_mid_prices"] = {}
        if "market_trend" not in trader_data:
            trader_data["market_trend"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
            
        last_mid = trader_data["last_mid_prices"].get(product, mid_price)
        
        # Get trend based on price history if available
        if product in trader_data["price_history"] and len(trader_data["price_history"][product]) >= 5:
            prices = trader_data["price_history"][product]
            
            # Calculate short and long moving averages
            short_ma = sum(prices[-3:]) / 3
            long_ma = sum(prices) / len(prices)
            
            # Use moving average crossover as trend signal
            if short_ma > long_ma:
                current_trend = 1  # Uptrend
            elif short_ma < long_ma:
                current_trend = -1  # Downtrend
            else:
                current_trend = 0  # No clear trend
        else:
            # Simple trend based on last price movement
            if mid_price > last_mid:
                current_trend = 1
            elif mid_price < last_mid:
                current_trend = -1
            else:
                current_trend = 0
                
        # Update the trend with exponential smoothing
        # Use a slower factor for trend to prevent jumping on noise
        old_trend = trader_data["market_trend"].get(product, 0)
        trader_data["market_trend"][product] = 0.8 * old_trend + 0.2 * current_trend
        
        # Update last mid price
        trader_data["last_mid_prices"][product] = mid_price
        
        return trader_data["market_trend"][product]
    
    def detect_drawdown(self, product, trader_data, position, mid_price):
        """Detect if we're in a drawdown period and adjust risk parameters."""
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
            
        if product not in trader_data["pnl_history"]:
            trader_data["pnl_history"][product] = []  # Use list instead of deque
        if product not in trader_data["position_history"]:
            trader_data["position_history"][product] = []
        if product not in trader_data["in_drawdown"]:
            trader_data["in_drawdown"][product] = False
            
        # Estimate current PnL
        last_position = trader_data["position_history"][product][-1] if trader_data["position_history"][product] else 0
        last_price = trader_data["last_mid_prices"].get(product, mid_price)
        
        # Simple PnL estimation based on position change and price change
        if last_position != position:
            # If position changed, record the result
            position_change = position - last_position
            price_change = mid_price - last_price
            trade_pnl = position_change * price_change
            
            # Record this PnL and maintain max length manually
            trader_data["pnl_history"][product].append(trade_pnl)
            if len(trader_data["pnl_history"][product]) > self.DRAWDOWN_PROTECTION["window_size"]:
                trader_data["pnl_history"][product] = trader_data["pnl_history"][product][-self.DRAWDOWN_PROTECTION["window_size"]:]
            
        # Update position history
        trader_data["position_history"][product].append(position)
        if len(trader_data["position_history"][product]) > 20:
            trader_data["position_history"][product] = trader_data["position_history"][product][-20:]
            
        # Check if we're in a drawdown
        if len(trader_data["pnl_history"][product]) >= self.DRAWDOWN_PROTECTION["window_size"]:
            recent_pnl = trader_data["pnl_history"][product]
            cumulative_pnl = sum(recent_pnl)
            
            # If cumulative PnL is negative beyond threshold, trigger drawdown protection
            if cumulative_pnl < -self.DRAWDOWN_PROTECTION["threshold"] * position_limit:
                trader_data["in_drawdown"][product] = True
            # If we're in a drawdown and see positive PnL, gradually recover
            elif trader_data["in_drawdown"][product] and cumulative_pnl > 0:
                # Gradually exit drawdown protection
                recovery_chance = self.DRAWDOWN_PROTECTION["recovery_factor"]
                if random.random() < recovery_chance:
                    trader_data["in_drawdown"][product] = False
        
        return trader_data["in_drawdown"].get(product, False), trader_data
    
    def should_take_order(self, product, price, fair_value, take_width, is_buy, regime, volatility):
        """Determine if we should take an existing order based on price and market regime."""
        # Adjust take width based on market regime and volatility
        adjusted_take_width = take_width
        
        if regime == "volatile":
            # More conservative in volatile markets
            adjusted_take_width = take_width * 1.5
        elif regime == "trending":
            # More aggressive in trending markets
            adjusted_take_width = take_width * 0.8
            
        # Add volatility adjustment
        volatility_adjustment = volatility * 100  # Scale up volatility
        adjusted_take_width += volatility_adjustment
        
        if is_buy:
            # For buy orders, we take if the price is below fair value - take width
            return price <= fair_value - adjusted_take_width
        else:
            # For sell orders, we take if the price is above fair value + take width
            return price >= fair_value + adjusted_take_width
            
    def take_best_orders(self, product, fair_value, orders, order_depth, position, params, regime, volatility, in_drawdown):
        """Take favorable orders from the market with regime awareness."""
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
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = abs(order_depth.sell_orders[best_ask])
            
            if self.should_take_order(product, best_ask, fair_value, take_width, True, regime, volatility):
                # Calculate how much we can buy based on position limits
                max_buy = effective_limit - position
                quantity = min(best_ask_amount, max_buy)
                
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity
        
        # Check for profitable buy orders (we sell)
        if len(order_depth.buy_orders) != 0:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            
            if self.should_take_order(product, best_bid, fair_value, take_width, False, regime, volatility):
                # Calculate how much we can sell based on position limits
                max_sell = effective_limit + position
                quantity = min(best_bid_amount, max_sell)
                
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity
                    
        return orders, buy_order_volume, sell_order_volume
    
    def calculate_fair_value(self, product, mid_price, trader_data, params, regime):
        """Calculate the fair value for a product using various signals and regime awareness."""
        alpha = params["alpha"]
        trend_factor = params["trend_factor"]
        
        # Initialize needed structures
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        
        # Adjust alpha based on regime
        if regime == "volatile":
            # Use faster-moving average in volatile markets
            alpha = min(0.6, alpha * 1.5)
        elif regime == "trending":
            # Use faster-moving average in trending markets
            alpha = min(0.5, alpha * 1.3)
        elif regime == "mean_reverting":
            # Use slower-moving average in mean-reverting markets
            alpha = max(0.1, alpha * 0.7)
        
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
                regime_trend_factor = trend_factor * 1.5
            elif regime == "mean_reverting":
                # Decrease trend following in mean-reverting markets
                regime_trend_factor = trend_factor * 0.5
            
            # Apply trend factor to fair value calculation
            trend_adjustment = trend * regime_trend_factor * trader_data["volatility"].get(product, 0.01) * mid_price
            
            if params["mean_reversion"] and regime != "trending":
                # For mean reverting products, move against the trend
                fair_value = new_ema - trend_adjustment
            else:
                # For trend following products, enhance the trend
                fair_value = new_ema + trend_adjustment
                
        return fair_value, trader_data
        
    def calculate_spread(self, product, fair_value, trader_data, params, regime, in_drawdown):
        """Calculate appropriate bid-ask spread based on volatility and market regime."""
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
            
        volatility = trader_data["volatility"].get(product, 0.01)
        spread_factor = params["spread_factor"]
        min_spread = params["min_spread"]
        
        # Adjust spread factor based on market regime
        if regime == "volatile":
            spread_factor *= 1.5  # Wider spreads in volatile markets
            min_spread = max(min_spread + 1, min_spread * 1.5)
        elif regime == "trending":
            spread_factor *= 0.9  # Tighter spreads in trending markets
        elif regime == "mean_reverting":
            spread_factor *= 1.2  # Moderate widening in mean-reverting markets
            
        # Further adjust if in drawdown protection mode
        if in_drawdown:
            spread_factor *= 1.5  # Much wider spreads during drawdown
            min_spread = max(min_spread + 2, min_spread * 2)
        
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
        
        # Increase spread as we approach position limits
        position_adjustment = math.ceil(position_ratio * position_ratio * base_spread * risk_aversion)
        
        return base_spread + position_adjustment
    
    def make_market(self, product, fair_value, spread, orders, position, trader_data, params, regime, in_drawdown):
        """Place market making orders with appropriate pricing and regime awareness."""
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
            aggressive_edge *= 0.7  # Less aggressive in volatile markets
        elif regime == "trending":
            aggressive_edge *= 1.2  # More aggressive in trending markets
            
        # Calculate appropriate bid and ask prices
        half_spread = spread / 2
        
        # If we have a large positive position, be more aggressive selling
        if position > 0:
            bid_price = math.floor(fair_value - half_spread * (1 + position / effective_limit))
            ask_price = math.ceil(fair_value + half_spread * (1 - aggressive_edge))
        # If we have a large negative position, be more aggressive buying
        elif position < 0:
            bid_price = math.floor(fair_value - half_spread * (1 - aggressive_edge))
            ask_price = math.ceil(fair_value + half_spread * (1 + abs(position) / effective_limit))
        # Balanced position
        else:
            bid_price = math.floor(fair_value - half_spread)
            ask_price = math.ceil(fair_value + half_spread)
            
        # Ensure minimum spread
        if ask_price - bid_price < params["min_spread"]:
            half_adjust = (params["min_spread"] - (ask_price - bid_price)) / 2
            bid_price = math.floor(bid_price - half_adjust)
            ask_price = math.ceil(ask_price + half_adjust)
            
        # Calculate order sizes
        buy_capacity = effective_limit - position
        sell_capacity = effective_limit + position
        
        # Place buy order
        if buy_capacity > 0:
            # Scale down order size in volatile or drawdown periods
            size_factor = 1.0
            if regime == "volatile":
                size_factor *= 0.8
            if in_drawdown:
                size_factor *= 0.7
                
            # Calculate adjusted buy size
            buy_size = max(1, math.floor(buy_capacity * size_factor))
            orders.append(Order(product, bid_price, buy_size))
            
        # Place sell order
        if sell_capacity > 0:
            # Scale down order size in volatile or drawdown periods
            size_factor = 1.0
            if regime == "volatile":
                size_factor *= 0.8
            if in_drawdown:
                size_factor *= 0.7
                
            # Calculate adjusted sell size
            sell_size = max(1, math.floor(sell_capacity * size_factor))
            orders.append(Order(product, ask_price, -sell_size))
            
        return orders
            
    def run(self, state: TradingState):
        """Main trading logic implementation."""
        try:
            # Load or initialize trader data
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except (json.JSONDecodeError, TypeError):
            trader_data = {}
            
        result = {}
        
        for product in state.order_depths:
            order_depth = state.order_depths[product]
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
                
            # Get current position
            current_position = state.position.get(product, 0)
            
            # Initialize current_position if needed
            if "current_position" not in trader_data:
                trader_data["current_position"] = {}
            trader_data["current_position"][product] = current_position
            
            # Get product-specific parameters
            params = self.get_product_params(product)
            
            # Check position limits
            position_limit = self.get_position_limit(product)
            
            # Calculate mid price
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            
            if best_bid >= best_ask:  # Check for crossed/invalid book
                continue
                
            mid_price = (best_bid + best_ask) / 2
            
            # Calculate volatility for this product
            volatility = self.calculate_volatility(product, mid_price, trader_data)
            
            # Detect market regime
            regime, trader_data = self.detect_market_regime(product, trader_data, mid_price)
            
            # Check for drawdown
            in_drawdown, trader_data = self.detect_drawdown(product, trader_data, current_position, mid_price)
            
            # Calculate fair value with regime awareness
            fair_value, trader_data = self.calculate_fair_value(
                product, mid_price, trader_data, params, regime
            )
            
            # Initialize orders list
            orders = []
            buy_order_volume = 0
            sell_order_volume = 0
            
            # Take profitable orders with regime awareness
            orders, buy_order_volume, sell_order_volume = self.take_best_orders(
                product, fair_value, orders, order_depth, current_position, 
                params, regime, volatility, in_drawdown
            )
            
            # Calculate appropriate spread for market making with regime awareness
            spread = self.calculate_spread(
                product, fair_value, trader_data, params, regime, in_drawdown
            )
            
            # Place market making orders with regime awareness
            orders = self.make_market(
                product, fair_value, spread, orders, current_position, 
                trader_data, params, regime, in_drawdown
            )
            
            if orders:
                result[product] = orders
                
        traderData = json.dumps(trader_data)
        conversions = 0
        
        return result, conversions, traderData