from typing import Dict, List
from datamodel import Order, OrderDepth, TradingState

class Trader:
    def __init__(self):
        self.position_limits = {
            "PICNIC_BASKET1": 60, "PICNIC_BASKET2": 100,
            "CROISSANTS": 250, "JAMS": 350, "DJEMBES": 60
        }
        self.base_profit_buffer = 1.5  # Lowered from 2.0
        self.basket1_composition = {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1}
        self.basket2_composition = {"CROISSANTS": 4, "JAMS": 2}
        self.price_history = {product: [] for product in self.position_limits.keys()}
        self.max_history = 5
        self.p_and_l = {product: 0.0 for product in self.position_limits.keys()}
        self.peak_p_and_l = 0.0
        self.drawdown_threshold = 0.05  # 5% drawdown triggers caution
        self.loss_unwind_threshold = 0.1  # 10% position loss triggers unwind

    def get_mid(self, product: str, state: TradingState) -> float:
        if product not in state.order_depths:
            return None
        bids = state.order_depths[product].buy_orders
        asks = state.order_depths[product].sell_orders
        if bids and asks:
            return (max(bids.keys()) + min(asks.keys())) / 2
        return None

    def update_price_history(self, state: TradingState):
        for product in self.position_limits:
            mid = self.get_mid(product, state)
            if mid:
                self.price_history[product].append(mid)
                if len(self.price_history[product]) > self.max_history:
                    self.price_history[product].pop(0)

    def get_volatility(self, product: str) -> float:
        prices = self.price_history[product]
        if len(prices) < 2:
            return 1.0
        diffs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        return sum(diffs) / len(diffs) if diffs else 1.0

    def within_limits(self, state: TradingState, product: str, qty: int) -> bool:
        current_position = state.position.get(product, 0)
        new_position = current_position + qty
        return abs(new_position) <= self.position_limits[product]

    def update_p_and_l(self, state: TradingState):
        total_pnl = 0.0
        for product in self.position_limits:
            if product in state.market_trades:
                for trade in state.market_trades[product]:
                    if product not in self.p_and_l:
                        self.p_and_l[product] = 0.0
                    self.p_and_l[product] += trade.quantity * trade.price
            total_pnl += self.p_and_l.get(product, 0.0)
        self.peak_p_and_l = max(self.peak_p_and_l, total_pnl)

    def unwind_position(self, state: TradingState, product: str, orders: Dict[str, List[Order]]):
        current_position = state.position.get(product, 0)
        if current_position == 0:
            return
        order_depth = state.order_depths[product]
        mid_price = self.get_mid(product, state)
        position_value = current_position * mid_price
        position_pnl = position_value - self.p_and_l.get(product, 0.0)
        # Unwind if position loss > 10%
        if abs(position_pnl / self.p_and_l.get(product, 1e-6)) > self.loss_unwind_threshold:
            if current_position > 0:
                best_bid = max(order_depth.buy_orders.keys())
                volume = min(order_depth.buy_orders[best_bid], current_position)
                if volume > 0 and self.within_limits(state, product, -volume):
                    orders[product] = orders.get(product, []) + [Order(product, best_bid, -volume)]
            elif current_position < 0:
                best_ask = min(order_depth.sell_orders.keys())
                volume = min(order_depth.sell_orders[best_ask], -current_position)
                if volume > 0 and self.within_limits(state, product, volume):
                    orders[product] = orders.get(product, []) + [Order(product, best_ask, volume)]

    def get_volume_scale(self, spread: float, buffer: float) -> float:
        # Scale volume with spread size
        return min(1.0, max(0.1, abs(spread) / (buffer * 2)))

    def run(self, state: TradingState) -> tuple[Dict[str, List[Order]], int, str]:
        orders: Dict[str, List[Order]] = {}
        self.update_price_history(state)
        self.update_p_and_l(state)

        # Check drawdown for cautious trading
        total_pnl = sum(self.p_and_l.values())
        drawdown = (self.peak_p_and_l - total_pnl) / (self.peak_p_and_l + 1e-6)
        volume_multiplier = 0.5 if drawdown > self.drawdown_threshold else 1.0

        # Get mid prices
        croissant_mid = self.get_mid("CROISSANTS", state)
        jam_mid = self.get_mid("JAMS", state)
        djembe_mid = self.get_mid("DJEMBES", state)
        basket1_mid = self.get_mid("PICNIC_BASKET1", state)
        basket2_mid = self.get_mid("PICNIC_BASKET2", state)

        # Adaptive profit buffer
        basket1_vol = self.get_volatility("PICNIC_BASKET1")
        basket2_vol = self.get_volatility("PICNIC_BASKET2")
        profit_buffer1 = min(self.base_profit_buffer + basket1_vol * 0.75, 4.0)
        profit_buffer2 = min(self.base_profit_buffer + basket2_vol * 0.75, 4.0)

        # PICNIC_BASKET1 Arbitrage
        if all([croissant_mid, jam_mid, djembe_mid, basket1_mid]):
            basket1_value = (self.basket1_composition["CROISSANTS"] * croissant_mid +
                             self.basket1_composition["JAMS"] * jam_mid +
                             self.basket1_composition["DJEMBES"] * djembe_mid)

            spread = basket1_mid - basket1_value
            volume_scale = self.get_volume_scale(spread, profit_buffer1) * volume_multiplier
            if spread > profit_buffer1:  # Sell basket
                best_bid = max(state.order_depths["PICNIC_BASKET1"].buy_orders.keys())
                max_volume = min(state.order_depths["PICNIC_BASKET1"].buy_orders[best_bid],
                                 self.position_limits["PICNIC_BASKET1"] - abs(state.position.get("PICNIC_BASKET1", 0)))
                volume = int(max_volume * volume_scale)
                if volume > 0 and self.within_limits(state, "PICNIC_BASKET1", -volume):
                    orders["PICNIC_BASKET1"] = [Order("PICNIC_BASKET1", best_bid, -volume)]
                    for product, qty in self.basket1_composition.items():
                        if self.within_limits(state, product, volume * qty):
                            best_ask = min(state.order_depths[product].sell_orders.keys())
                            avail_volume = min(state.order_depths[product].sell_orders[best_ask], volume * qty)
                            if avail_volume > 0:
                                orders[product] = orders.get(product, []) + [Order(product, best_ask, avail_volume)]
            elif spread < -profit_buffer1:  # Buy basket
                best_ask = min(state.order_depths["PICNIC_BASKET1"].sell_orders.keys())
                max_volume = min(state.order_depths["PICNIC_BASKET1"].sell_orders[best_ask],
                                 self.position_limits["PICNIC_BASKET1"] - abs(state.position.get("PICNIC_BASKET1", 0)))
                volume = int(max_volume * volume_scale)
                if volume > 0 and self.within_limits(state, "PICNIC_BASKET1", volume):
                    orders["PICNIC_BASKET1"] = [Order("PICNIC_BASKET1", best_ask, volume)]
                    for product, qty in self.basket1_composition.items():
                        if self.within_limits(state, product, -volume * qty):
                            best_bid = max(state.order_depths[product].buy_orders.keys())
                            avail_volume = min(state.order_depths[product].buy_orders[best_bid], volume * qty)
                            if avail_volume > 0:
                                orders[product] = orders.get(product, []) + [Order(product, best_bid, -avail_volume)]
            elif abs(spread) < profit_buffer1 / 2:
                self.unwind_position(state, "PICNIC_BASKET1", orders)
                for product in self.basket1_composition:
                    self.unwind_position(state, product, orders)

        # PICNIC_BASKET2 Arbitrage
        if all([croissant_mid, jam_mid, basket2_mid]):
            basket2_value = (self.basket2_composition["CROISSANTS"] * croissant_mid +
                             self.basket2_composition["JAMS"] * jam_mid)

            spread = basket2_mid - basket2_value
            volume_scale = self.get_volume_scale(spread, profit_buffer2) * volume_multiplier
            if spread > profit_buffer2:  # Sell basket
                best_bid = max(state.order_depths["PICNIC_BASKET2"].buy_orders.keys())
                max_volume = min(state.order_depths["PICNIC_BASKET2"].buy_orders[best_bid],
                                 self.position_limits["PICNIC_BASKET2"] - abs(state.position.get("PICNIC_BASKET2", 0)))
                volume = int(max_volume * volume_scale)
                if volume > 0 and self.within_limits(state, "PICNIC_BASKET2", -volume):
                    orders["PICNIC_BASKET2"] = [Order("PICNIC_BASKET2", best_bid, -volume)]
                    for product, qty in self.basket2_composition.items():
                        if self.within_limits(state, product, volume * qty):
                            best_ask = min(state.order_depths[product].sell_orders.keys())
                            avail_volume = min(state.order_depths[product].sell_orders[best_ask], volume * qty)
                            if avail_volume > 0:
                                orders[product] = orders.get(product, []) + [Order(product, best_ask, avail_volume)]
            elif spread < -profit_buffer2:  # Buy basket
                best_ask = min(state.order_depths["PICNIC_BASKET2"].sell_orders.keys())
                max_volume = min(state.order_depths["PICNIC_BASKET2"].sell_orders[best_ask],
                                 self.position_limits["PICNIC_BASKET2"] - abs(state.position.get("PICNIC_BASKET2", 0)))
                volume = int(max_volume * volume_scale)
                if volume > 0 and self.within_limits(state, "PICNIC_BASKET2", volume):
                    orders["PICNIC_BASKET2"] = [Order("PICNIC_BASKET2", best_ask, volume)]
                    for product, qty in self.basket2_composition.items():
                        if self.within_limits(state, product, -volume * qty):
                            best_bid = max(state.order_depths[product].buy_orders.keys())
                            avail_volume = min(state.order_depths[product].buy_orders[best_bid], volume * qty)
                            if avail_volume > 0:
                                orders[product] = orders.get(product, []) + [Order(product, best_bid, -avail_volume)]
            elif abs(spread) < profit_buffer2 / 2:
                self.unwind_position(state, "PICNIC_BASKET2", orders)
                for product in self.basket2_composition:
                    self.unwind_position(state, product, orders)

        return orders, 0, "OPTIMIZED_ARBITRAGE"