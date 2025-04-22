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
        "CROISSANTS": 250,  # Adjusted spelling to match data
        "JAMS": 350,        # Adjusted spelling to match data
        "DJEMBES": 60,      # Adjusted spelling to match data
        "VOLCANIC_ROCK": 400,
        "VOLCANIC_ROCK_VOUCHER_9500": 200,
        "VOLCANIC_ROCK_VOUCHER_9750": 200,
        "VOLCANIC_ROCK_VOUCHER_10000": 200,
        "VOLCANIC_ROCK_VOUCHER_10250": 200,
        "VOLCANIC_ROCK_VOUCHER_10500": 200,
        "DEFAULT": 20
    }
    
    # Basket compositions for arbitrage
    BASKET_COMPOSITION = {
        "PICNIC_BASKET1": {
            "CROISSANTS": 6,
            "JAMS": 3,
            "DJEMBES": 1
        },
        "PICNIC_BASKET2": {
            "CROISSANTS": 4,
            "JAMS": 2
            # "DJEMBES": 0
        }
    }
    
    # Product-specific parameters
    PRODUCT_PARAMS = {
        "PICNIC_BASKET1": {
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
        "DJEMBES": {
            "alpha": 0.4,
            "spread_factor": 0.7,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 2,
            "take_width": 3,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.5,
            "max_position_scale": 0.9,
        },
        "CROISSANTS": {
            "alpha": 0.35,
            "spread_factor": 0.6,
            "trend_factor": 0.6,
            "mean_reversion": True,
            "volatility_scale": 1.3,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.6,
            "risk_aversion": 0.4,
            "max_position_scale": 1.0,
        },
        "JAMS": {
            "alpha": 0.35,
            "spread_factor": 0.6,
            "trend_factor": 0.7,
            "mean_reversion": True,
            "volatility_scale": 1.4,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.6,
            "risk_aversion": 0.4,
            "max_position_scale": 1.0,
        },
        "VOLCANIC_ROCK": {
            "alpha": 0.35,
            "spread_factor": 0.6,
            "trend_factor": 0.7,
            "mean_reversion": True,
            "volatility_scale": 1.4,
            "min_spread": 2,
            "take_width": 3,
            "aggressive_edge": 0.6,
            "risk_aversion": 0.4,
            "max_position_scale": 1.0,
        },
        "VOLCANIC_ROCK_VOUCHER_9500": {
            "alpha": 0.45,
            "spread_factor": 0.5,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.3,
            "max_position_scale": 0.9,
        },
        "VOLCANIC_ROCK_VOUCHER_9750": {
            "alpha": 0.45,
            "spread_factor": 0.5,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.3,
            "max_position_scale": 0.9,
        },
        "VOLCANIC_ROCK_VOUCHER_10000": {
            "alpha": 0.45,
            "spread_factor": 0.5,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.3,
            "max_position_scale": 0.9,
        },
        "VOLCANIC_ROCK_VOUCHER_10250": {
            "alpha": 0.45,
            "spread_factor": 0.5,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.3,
            "max_position_scale": 0.9,
        },
        "VOLCANIC_ROCK_VOUCHER_10500": {
            "alpha": 0.45,
            "spread_factor": 0.5,
            "trend_factor": 0.8,
            "mean_reversion": False,
            "volatility_scale": 1.6,
            "min_spread": 1,
            "take_width": 2,
            "aggressive_edge": 0.7,
            "risk_aversion": 0.3,
            "max_position_scale": 0.9,
        }
    }
    
    # Default parameters for any new product
    DEFAULT_PARAMS = {
        "alpha": 0.35,
        "spread_factor": 0.6,
        "trend_factor": 0.6,
        "mean_reversion": True,
        "volatility_scale": 1.2,
        "min_spread": 1,
        "take_width": 2,
        "aggressive_edge": 0.6,
        "risk_aversion": 0.4,
        "max_position_scale": 1.0,
    }
    
    # Arbitrage parameters
    ARBITRAGE_PARAMS = {
        "min_profit_per_lot": 1,
        "max_arbitrage_lots": 10,
        "aggressive_factor": 1.0,
        "basket_discount": 0.97,
        "voucher_premium_factor": 1.1,  # Premium over intrinsic value for vouchers
    }
    
    # Drawdown protection parameters
    DRAWDOWN_PROTECTION = {
        "window_size": 8,
        "threshold": 0.04,
        "reduction_factor": 0.6,
        "recovery_factor": 0.3,
    }
    
    def __init__(self):
        self.price_history = {}
        self.volatility = {}
        self.ema_prices = {}
        self.last_mid_prices = {}
        self.position_history = {}
        self.market_trend = {}
        self.pnl_history = {}
        self.market_regime = {}
        self.success_rate = {}
        self.fair_values = {}
        self.arbitrage_executed = {}
        
    def get_position_limit(self, product):
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])
        
    def get_product_params(self, product):
        return self.PRODUCT_PARAMS.get(product, self.DEFAULT_PARAMS)
    
    def detect_market_regime(self, product, trader_data, current_price):
        if "market_regime" not in trader_data:
            trader_data["market_regime"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        
        if product not in trader_data["price_history"] or len(trader_data["price_history"].get(product, [])) < 5:
            trader_data["market_regime"][product] = "normal"
            return "normal", trader_data
            
        prices = trader_data["price_history"][product][-8:]
        
        consecutive_up = 0
        consecutive_down = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                consecutive_up += 1
                consecutive_down = 0
            elif prices[i] < prices[i-1]:
                consecutive_down += 1
                consecutive_up = 0
        
        recent_volatility = trader_data["volatility"].get(product, 0.01)
        avg_price = sum(prices) / len(prices)
        price_deviation = abs(current_price - avg_price) / avg_price
        trend_strength = abs(prices[-1] - prices[0]) / (max(prices) - min(prices) + 0.001)
        
        if (consecutive_up >= 3 or consecutive_down >= 3) and trend_strength > 0.5:
            regime = "trending"
        elif recent_volatility > 0.025:
            regime = "volatile"
        elif price_deviation > 0.015:
            regime = "mean_reverting"
        else:
            regime = "normal"
            
        old_regime = trader_data["market_regime"].get(product, "normal")
        if old_regime != regime:
            if (regime == "volatile" and recent_volatility > 0.035) or \
               (regime == "trending" and (consecutive_up >= 3 or consecutive_down >= 3)) or \
               (regime == "mean_reverting" and price_deviation > 0.025):
                trader_data["market_regime"][product] = regime
            else:
                regime = old_regime
        
        return regime, trader_data
    
    def calculate_volatility(self, product, mid_price, trader_data):
        history_len = 20
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        
        if product not in trader_data["price_history"]:
            trader_data["price_history"][product] = []
        
        trader_data["price_history"][product].append(mid_price)
        if len(trader_data["price_history"][product]) > history_len:
            trader_data["price_history"][product] = trader_data["price_history"][product][-history_len:]
        
        if len(trader_data["price_history"][product]) >= 3:
            price_changes = [
                abs((trader_data["price_history"][product][i] / trader_data["price_history"][product][i-1]) - 1) 
                for i in range(1, len(trader_data["price_history"][product]))
            ]
            if len(price_changes) > 0:
                volatility = statistics.stdev(price_changes) if len(price_changes) > 1 else price_changes[0]
                old_volatility = trader_data["volatility"].get(product, volatility)
                trader_data["volatility"][product] = 0.8 * old_volatility + 0.2 * volatility
                return trader_data["volatility"][product]
        
        if product not in trader_data["volatility"]:
            trader_data["volatility"][product] = 0.01
        return trader_data["volatility"][product]
    
    def calculate_trend(self, product, mid_price, trader_data):
        if "last_mid_prices" not in trader_data:
            trader_data["last_mid_prices"] = {}
        if "market_trend" not in trader_data:
            trader_data["market_trend"] = {}
        if "price_history" not in trader_data:
            trader_data["price_history"] = {}
            
        last_mid = trader_data["last_mid_prices"].get(product, mid_price)
        
        if product in trader_data["price_history"] and len(trader_data["price_history"][product]) >= 6:
            prices = trader_data["price_history"][product]
            short_ma = sum(prices[-3:]) / 3
            med_ma = sum(prices[-6:]) / 6
            long_ma = sum(prices) / len(prices)
            
            if short_ma > med_ma and med_ma > long_ma:
                current_trend = 1.5
            elif short_ma > med_ma:
                current_trend = 1.0
            elif short_ma < med_ma and med_ma < long_ma:
                current_trend = -1.5
            elif short_ma < med_ma:
                current_trend = -1.0
            else:
                current_trend = 0
                
            if len(prices) >= 4:
                recent_change = (prices[-1] - prices[-4]) / prices[-4]
                momentum = 0.5 * (1 if recent_change > 0 else -1 if recent_change < 0 else 0)
                current_trend += momentum
        else:
            price_change_pct = (mid_price - last_mid) / last_mid if last_mid != 0 else 0
            if price_change_pct > 0.005:
                current_trend = 1.5
            elif price_change_pct > 0:
                current_trend = 1
            elif price_change_pct < -0.005:
                current_trend = -1.5
            elif price_change_pct < 0:
                current_trend = -1
            else:
                current_trend = 0
                
        old_trend = trader_data["market_trend"].get(product, 0)
        trader_data["market_trend"][product] = 0.7 * old_trend + 0.3 * current_trend
        trader_data["last_mid_prices"][product] = mid_price
        
        return trader_data["market_trend"][product]
    
    def detect_drawdown(self, product, trader_data, position, mid_price):
        position_limit = self.get_position_limit(product)
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
            
        last_position = trader_data["position_history"][product][-1] if trader_data["position_history"][product] else 0
        last_price = trader_data["last_mid_prices"].get(product, mid_price)
        
        if last_position != position:
            position_change = position - last_position
            price_change = mid_price - last_price
            trade_pnl = position_change * price_change
            trader_data["pnl_history"][product].append(trade_pnl)
            if len(trader_data["pnl_history"][product]) > self.DRAWDOWN_PROTECTION["window_size"]:
                trader_data["pnl_history"][product] = trader_data["pnl_history"][product][-self.DRAWDOWN_PROTECTION["window_size"]:]
        
        trader_data["position_history"][product].append(position)
        if len(trader_data["position_history"][product]) > 25:
            trader_data["position_history"][product] = trader_data["position_history"][product][-25:]
            
        if len(trader_data["pnl_history"][product]) >= self.DRAWDOWN_PROTECTION["window_size"]:
            recent_pnl = trader_data["pnl_history"][product]
            cumulative_pnl = sum(recent_pnl)
            if cumulative_pnl < -self.DRAWDOWN_PROTECTION["threshold"] * position_limit:
                trader_data["in_drawdown"][product] = True
                trader_data["drawdown_counter"][product] = 0
            elif trader_data["in_drawdown"][product]:
                trader_data["drawdown_counter"][product] += 1
                if cumulative_pnl > 0 or trader_data["drawdown_counter"][product] >= 10:
                    recovery_chance = self.DRAWDOWN_PROTECTION["recovery_factor"] * (1 + trader_data["drawdown_counter"][product] / 10)
                    if random.random() < min(recovery_chance, 0.8):
                        trader_data["in_drawdown"][product] = False
                        trader_data["drawdown_counter"][product] = 0
        
        return trader_data["in_drawdown"].get(product, False), trader_data
    
    def should_take_order(self, product, price, fair_value, take_width, is_buy, regime, volatility):
        adjusted_take_width = take_width
        if regime == "volatile":
            adjusted_take_width = take_width * 1.4
        elif regime == "trending":
            adjusted_take_width = take_width * 0.7
        elif regime == "mean_reverting":
            adjusted_take_width = take_width * 0.75
            
        volatility_adjustment = volatility * 80
        adjusted_take_width += volatility_adjustment
        adjusted_take_width = max(1, min(adjusted_take_width, take_width * 2))
        
        if is_buy:
            return price <= fair_value - adjusted_take_width
        else:
            return price >= fair_value + adjusted_take_width
            
    def take_best_orders(self, product, fair_value, orders, order_depth, position, params, regime, volatility, in_drawdown):
        take_width = params["take_width"]
        position_limit = self.get_position_limit(product)
        effective_limit = position_limit
        if in_drawdown:
            effective_limit = math.floor(position_limit * self.DRAWDOWN_PROTECTION["reduction_factor"])
        effective_limit = math.floor(effective_limit * params["max_position_scale"])
        
        buy_order_volume = 0
        sell_order_volume = 0
        
        if len(order_depth.sell_orders) != 0:
            sell_prices = sorted(order_depth.sell_orders.keys())
            for price in sell_prices:
                amount = abs(order_depth.sell_orders[price])
                if self.should_take_order(product, price, fair_value, take_width, True, regime, volatility):
                    max_buy = effective_limit - position - buy_order_volume
                    quantity = min(amount, max_buy)
                    orders.append(Order(product, price, quantity))
                    buy_order_volume += quantity
                    if buy_order_volume >= max_buy:
                        break
                else:
                    break
        
        if len(order_depth.buy_orders) != 0:
            buy_prices = sorted(order_depth.buy_orders.keys(), reverse=True)
            for price in buy_prices:
                amount = order_depth.buy_orders[price]
                if self.should_take_order(product, price, fair_value, take_width, False, regime, volatility):
                    max_sell = effective_limit + position - sell_order_volume
                    quantity = min(amount, max_sell)
                    orders.append(Order(product, price, -quantity))
                    sell_order_volume += quantity
                    if sell_order_volume >= max_sell:
                        break
                else:
                    break
                    
        return orders, buy_order_volume, sell_order_volume
    
    def calculate_fair_value(self, product, mid_price, trader_data, params, regime):
        alpha = params["alpha"]
        trend_factor = params["trend_factor"]
        
        if "ema_prices" not in trader_data:
            trader_data["ema_prices"] = {}
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "fair_values" not in trader_data:
            trader_data["fair_values"] = {}
        
        if regime == "volatile":
            alpha = min(0.7, alpha * 1.5)
        elif regime == "trending":
            alpha = min(0.6, alpha * 1.3)
        elif regime == "mean_reverting":
            alpha = max(0.15, alpha * 0.7)
        
        if product not in trader_data["ema_prices"]:
            trader_data["ema_prices"][product] = mid_price
            fair_value = mid_price
        else:
            old_ema = trader_data["ema_prices"][product]
            new_ema = alpha * mid_price + (1 - alpha) * old_ema
            trader_data["ema_prices"][product] = new_ema
            
            trend = self.calculate_trend(product, mid_price, trader_data)
            regime_trend_factor = trend_factor
            if regime == "trending":
                regime_trend_factor = trend_factor * 1.7
            elif regime == "mean_reverting":
                regime_trend_factor = trend_factor * 0.4
            
            trend_adjustment = trend * regime_trend_factor * trader_data["volatility"].get(product, 0.01) * mid_price
            if params["mean_reversion"] and regime != "trending":
                fair_value = new_ema - trend_adjustment
            else:
                fair_value = new_ema + trend_adjustment
        
        trader_data["fair_values"][product] = fair_value
        return fair_value, trader_data
        
    def calculate_spread(self, product, fair_value, trader_data, params, regime, in_drawdown):
        if "volatility" not in trader_data:
            trader_data["volatility"] = {}
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
            
        volatility = trader_data["volatility"].get(product, 0.01)
        spread_factor = params["spread_factor"]
        min_spread = params["min_spread"]
        
        if regime == "volatile":
            spread_factor *= 1.4
            min_spread = max(min_spread + 1, min_spread * 1.4)
        elif regime == "trending":
            spread_factor *= 0.8
            min_spread = max(1, min_spread - 1)
        elif regime == "mean_reverting":
            spread_factor *= 1.1
            
        if in_drawdown:
            spread_factor *= 1.3
            min_spread = max(min_spread + 1, min_spread * 1.5)
        
        base_spread = max(
            min_spread, 
            math.ceil(volatility * params["volatility_scale"] * fair_value * spread_factor)
        )
        
        position = trader_data["current_position"].get(product, 0)
        position_limit = self.get_position_limit(product)
        position_ratio = abs(position) / position_limit if position_limit > 0 else 0
        risk_aversion = params["risk_aversion"]
        position_adjustment = math.ceil(math.log(1 + 5 * position_ratio) * base_spread * risk_aversion)
        
        return base_spread + position_adjustment
    
    def make_market(self, product, fair_value, spread, orders, position, trader_data, params, regime, in_drawdown):
        position_limit = self.get_position_limit(product)
        aggressive_edge = params["aggressive_edge"]
        
        effective_limit = position_limit
        if in_drawdown:
            effective_limit = math.floor(position_limit * self.DRAWDOWN_PROTECTION["reduction_factor"])
        effective_limit = math.floor(effective_limit * params["max_position_scale"])
        
        if regime == "volatile":
            aggressive_edge *= 0.8
        elif regime == "trending":
            aggressive_edge *= 1.3
        elif regime == "mean_reverting":
            aggressive_edge *= 1.1
        
        half_spread = spread / 2
        if "market_trend" not in trader_data:
            trader_data["market_trend"] = {}
        trend = trader_data["market_trend"].get(product, 0)
        position_bias = -position / effective_limit if effective_limit > 0 else 0
        bias_factor = (trend * 0.3) + (position_bias * 0.7)
        bias_adjustment = half_spread * bias_factor * 0.5
        
        bid_price = math.floor(fair_value - half_spread + bias_adjustment)
        ask_price = math.ceil(fair_value + half_spread + bias_adjustment)
        
        if ask_price - bid_price < params["min_spread"]:
            spread_adjustment = (params["min_spread"] - (ask_price - bid_price)) / 2
            bid_price = math.floor(bid_price - spread_adjustment)
            ask_price = math.ceil(ask_price + spread_adjustment)
        
        remaining_buy = effective_limit - position
        remaining_sell = effective_limit + position
        base_size = max(1, int(effective_limit * 0.1))
        
        if regime == "volatile":
            base_size = max(1, int(base_size * 0.8))
        elif regime == "trending":
            base_size = max(1, int(base_size * 1.3))
        if in_drawdown:
            base_size = max(1, int(base_size * 0.7))
            
        buy_size = min(remaining_buy, math.ceil(base_size * (1 + aggressive_edge * (1 - position_bias))))
        sell_size = min(remaining_sell, math.ceil(base_size * (1 + aggressive_edge * (1 + position_bias))))
        
        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))
            
        return orders
    
    def manage_basket_arbitrage(self, products, inventory, trader_data, order_depths, orders):
        if "fair_values" not in trader_data:
            trader_data["fair_values"] = {}
        if "arbitrage_executed" not in trader_data:
            trader_data["arbitrage_executed"] = {}
            
        # Traditional basket arbitrage
        for basket_name, composition in self.BASKET_COMPOSITION.items():
            if basket_name not in products:
                continue
            all_components_available = all(component in products for component in composition)
            if not all_components_available:
                continue
                
            basket_position = inventory.get(basket_name, 0)
            basket_position_limit = self.get_position_limit(basket_name)
            basket_depth = order_depths.get(basket_name)
            if not basket_depth:
                continue
                
            component_value = 0
            component_limits_ok = True
            component_positions = {}
            for component, quantity in composition.items():
                component_position = inventory.get(component, 0)
                component_limit = self.get_position_limit(component)
                component_positions[component] = component_position
                if component in trader_data["fair_values"]:
                    component_value += trader_data["fair_values"][component] * quantity
                else:
                    component_depth = order_depths.get(component)
                    if not component_depth or not component_depth.buy_orders or not component_depth.sell_orders:
                        component_limits_ok = False
                        break
                    component_mid = (max(component_depth.buy_orders.keys()) + min(component_depth.sell_orders.keys())) / 2
                    component_value += component_mid * quantity
            
            if not component_limits_ok:
                continue
                
            expected_basket_value = component_value * self.ARBITRAGE_PARAMS["basket_discount"]
            if basket_name not in trader_data["arbitrage_executed"]:
                trader_data["arbitrage_executed"][basket_name] = {
                    "buy_basket_sell_components": 0,
                    "buy_components_sell_basket": 0
                }
            
            if basket_depth.sell_orders:
                basket_ask = min(basket_depth.sell_orders.keys())
                basket_ask_volume = abs(basket_depth.sell_orders[basket_ask])
                potential_profit = expected_basket_value - basket_ask
                if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                    max_baskets = min(
                        basket_ask_volume,
                        self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                        basket_position_limit - basket_position
                    )
                    for component, quantity in composition.items():
                        component_position = component_positions[component]
                        component_limit = self.get_position_limit(component)
                        max_component_lots = (component_limit - component_position) // quantity
                        max_baskets = min(max_baskets, max_component_lots)
                    if max_baskets > 0:
                        orders.append(Order(basket_name, basket_ask, max_baskets))
                        for component, quantity in composition.items():
                            component_depth = order_depths.get(component)
                            if component_depth and component_depth.buy_orders:
                                component_bid = max(component_depth.buy_orders.keys())
                                orders.append(Order(component, component_bid, -max_baskets * quantity))
                        trader_data["arbitrage_executed"][basket_name]["buy_basket_sell_components"] += max_baskets
            
            if basket_depth.buy_orders:
                basket_bid = max(basket_depth.buy_orders.keys())
                basket_bid_volume = basket_depth.buy_orders[basket_bid]
                potential_profit = basket_bid - expected_basket_value
                if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                    max_baskets = min(
                        basket_bid_volume,
                        self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                        basket_position_limit + basket_position
                    )
                    for component, quantity in composition.items():
                        component_position = component_positions[component]
                        component_limit = self.get_position_limit(component)
                        max_component_lots = (component_position + component_limit) // quantity
                        max_baskets = min(max_baskets, max_component_lots)
                    if max_baskets > 0:
                        orders.append(Order(basket_name, basket_bid, -max_baskets))
                        for component, quantity in composition.items():
                            component_depth = order_depths.get(component)
                            if component_depth and component_depth.sell_orders:
                                component_ask = min(component_depth.sell_orders.keys())
                                orders.append(Order(component, component_ask, max_baskets * quantity))
                        trader_data["arbitrage_executed"][basket_name]["buy_components_sell_basket"] += max_baskets
        
        # Voucher-Rock arbitrage
        rock_product = "VOLCANIC_ROCK"
        if rock_product in products and rock_product in trader_data["fair_values"]:
            rock_fair_value = trader_data["fair_values"][rock_product]
            rock_depth = order_depths.get(rock_product)
            rock_position = inventory.get(rock_product, 0)
            rock_position_limit = self.get_position_limit(rock_product)
            
            voucher_strikes = {
                "VOLCANIC_ROCK_VOUCHER_9500": 9500,
                "VOLCANIC_ROCK_VOUCHER_9750": 9750,
                "VOLCANIC_ROCK_VOUCHER_10000": 10000,
                "VOLCANIC_ROCK_VOUCHER_10250": 10250,
                "VOLCANIC_ROCK_VOUCHER_10500": 10500
            }
            
            for voucher, strike in voucher_strikes.items():
                if voucher not in products:
                    continue
                voucher_depth = order_depths.get(voucher)
                if not voucher_depth:
                    continue
                voucher_position = inventory.get(voucher, 0)
                voucher_position_limit = self.get_position_limit(voucher)
                
                # Calculate intrinsic value
                intrinsic_value = max(0, rock_fair_value - strike)
                # Adjust for time value (simplified: premium decreases as expiration nears)
                days_to_expiry = 4  # Round 3 context
                time_value = intrinsic_value * (days_to_expiry / 7) * self.ARBITRAGE_PARAMS["voucher_premium_factor"]
                fair_voucher_value = intrinsic_value + time_value
                
                if voucher not in trader_data["arbitrage_executed"]:
                    trader_data["arbitrage_executed"][voucher] = {
                        "buy_voucher_sell_rock": 0,
                        "buy_rock_sell_voucher": 0
                    }
                
                # Buy voucher, sell rock
                if voucher_depth.sell_orders and rock_depth and rock_depth.buy_orders:
                    voucher_ask = min(voucher_depth.sell_orders.keys())
                    voucher_ask_volume = abs(voucher_depth.sell_orders[voucher_ask])
                    rock_bid = max(rock_depth.buy_orders.keys())
                    potential_profit = (rock_bid - strike) - voucher_ask
                    if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                        max_lots = min(
                            voucher_ask_volume,
                            rock_depth.buy_orders[rock_bid],
                            self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                            voucher_position_limit - voucher_position,
                            rock_position_limit + rock_position
                        )
                        if max_lots > 0:
                            orders.append(Order(voucher, voucher_ask, max_lots))
                            orders.append(Order(rock_product, rock_bid, -max_lots))
                            trader_data["arbitrage_executed"][voucher]["buy_voucher_sell_rock"] += max_lots
                
                # Buy rock, sell voucher
                if voucher_depth.buy_orders and rock_depth and rock_depth.sell_orders:
                    voucher_bid = max(voucher_depth.buy_orders.keys())
                    voucher_bid_volume = voucher_depth.buy_orders[voucher_bid]
                    rock_ask = min(rock_depth.sell_orders.keys())
                    potential_profit = voucher_bid - max(0, rock_ask - strike)
                    if potential_profit >= self.ARBITRAGE_PARAMS["min_profit_per_lot"]:
                        max_lots = min(
                            voucher_bid_volume,
                            abs(rock_depth.sell_orders[rock_ask]),
                            self.ARBITRAGE_PARAMS["max_arbitrage_lots"],
                            voucher_position_limit + voucher_position,
                            rock_position_limit - rock_position
                        )
                        if max_lots > 0:
                            orders.append(Order(voucher, voucher_bid, -max_lots))
                            orders.append(Order(rock_product, rock_ask, max_lots))
                            trader_data["arbitrage_executed"][voucher]["buy_rock_sell_voucher"] += max_lots
        
        return orders, trader_data
    
    def run(self, state: TradingState):
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except (json.JSONDecodeError, TypeError):
            trader_data = {}
            
        result = {}
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
        
        for product in state.position:
            trader_data["current_position"][product] = state.position.get(product, 0)
            
        if len(state.order_depths) > 1:
            arbitrage_orders = []
            arbitrage_orders, trader_data = self.manage_basket_arbitrage(
                state.order_depths.keys(),
                state.position,
                trader_data,
                state.order_depths,
                arbitrage_orders
            )
            for order in arbitrage_orders:
                if order.symbol not in result:
                    result[order.symbol] = []
                result[order.symbol].append(order)
            
        for product in state.order_depths.keys():
            if product not in state.position:
                continue
                
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            
            if not order_depth.buy_orders and not order_depth.sell_orders:
                continue
                
            if len(order_depth.sell_orders) > 0 and len(order_depth.buy_orders) > 0:
                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())
                if best_bid >= best_ask:
                    continue
                mid_price = (best_bid + best_ask) / 2
            elif len(order_depth.sell_orders) > 0:
                mid_price = min(order_depth.sell_orders.keys())
            else:
                mid_price = max(order_depth.buy_orders.keys())
                
            params = self.get_product_params(product)
            volatility = self.calculate_volatility(product, mid_price, trader_data)
            regime, trader_data = self.detect_market_regime(product, trader_data, mid_price)
            in_drawdown, trader_data = self.detect_drawdown(product, trader_data, position, mid_price)
            fair_value, trader_data = self.calculate_fair_value(product, mid_price, trader_data, params, regime)
            
            orders = []
            orders, buy_order_volume, sell_order_volume = self.take_best_orders(
                product, fair_value, orders, order_depth, position, 
                params, regime, volatility, in_drawdown
            )
            
            adjusted_position = position + buy_order_volume - sell_order_volume
            trader_data["current_position"][product] = adjusted_position
            spread = self.calculate_spread(product, fair_value, trader_data, params, regime, in_drawdown)
            orders = self.make_market(
                product, fair_value, spread, orders, adjusted_position, 
                trader_data, params, regime, in_drawdown
            )
            
            if orders:
                result[product] = orders
                
        traderData = json.dumps(trader_data)
        conversions = 0
        
        return result, conversions, traderData