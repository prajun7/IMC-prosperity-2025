import json
import math
import statistics
from datamodel import OrderDepth, TradingState, Order

class Trader:
    # Position limits for each product
    POSITION_LIMITS = {
        "PICNIC_BASKET1": 60,
        "PICNIC_BASKET2": 100,
        "CROISSANTS": 250,
        "JAMS": 350,
        "DJEMBES": 60,
        "VOLCANIC_ROCK": 400,
        "VOLCANIC_ROCK_VOUCHER_9500": 200,
        "VOLCANIC_ROCK_VOUCHER_9750": 200,
        "VOLCANIC_ROCK_VOUCHER_10000": 200,
        "VOLCANIC_ROCK_VOUCHER_10250": 200,
        "VOLCANIC_ROCK_VOUCHER_10500": 200,
        "DEFAULT": 20
    }

    # Define vouchers (product name, strike price)
    VOUCHERS = [
        ("VOLCANIC_ROCK_VOUCHER_9500", 9500),
        ("VOLCANIC_ROCK_VOUCHER_9750", 9750),
        ("VOLCANIC_ROCK_VOUCHER_10000", 10000),
        ("VOLCANIC_ROCK_VOUCHER_10250", 10250),
        ("VOLCANIC_ROCK_VOUCHER_10500", 10500)
    ]
    ROCK_PRODUCT = "VOLCANIC_ROCK"
    T = 4  # Time to expiration in days (Round 3, expires in 7 days from Round 1)

    def norm_cdf(self, x):
        """Approximate cumulative normal distribution function."""
        if x > 6:
            return 1.0
        if x < -6:
            return 0.0
        t = 1 / (1 + 0.2316419 * abs(x))
        c = (0.31938153 * t - 0.356563782 * t**2 + 1.781477937 * t**3 -
             1.821255978 * t**4 + 1.330274429 * t**5)
        n = 1 - c * (1 / math.sqrt(2 * math.pi)) * math.exp(-x**2 / 2)
        return n if x >= 0 else 1 - n

    def black_scholes_call(self, S, K, T, sigma):
        """Calculate call option price using Black-Scholes model."""
        if T <= 0 or sigma <= 0:
            return max(0, S - K)
        d1 = (math.log(S / K) + (sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return S * self.norm_cdf(d1) - K * self.norm_cdf(d2)

    def black_scholes_delta(self, S, K, T, sigma):
        """Calculate delta of a call option."""
        if T <= 0 or sigma <= 0:
            return 1 if S > K else 0
        d1 = (math.log(S / K) + (sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        return self.norm_cdf(d1)

    def get_position_limit(self, product):
        """Retrieve position limit for a given product."""
        return self.POSITION_LIMITS.get(product, self.POSITION_LIMITS["DEFAULT"])

    def run(self, state: TradingState) -> tuple[Dict[str, List[Order]], int, str]:
        """
        Main trading logic executed each iteration.
        
        Args:
            state (TradingState): Current market state including order depths and positions.
        
        Returns:
            tuple: (result: Dict[str, List[Order]], conversions: int, traderData: str)
        """
        result = {}
        # Load trader data or initialize if empty
        trader_data = json.loads(state.traderData) if state.traderData else {}
        if "current_position" not in trader_data:
            trader_data["current_position"] = {}
        for product in state.position:
            trader_data["current_position"][product] = state.position.get(product, 0)

        # Basic market-making for non-voucher/rock products
        for product in state.order_depths:
            if product in [self.ROCK_PRODUCT] + [v[0] for v in self.VOUCHERS]:
                continue
            order_depth = state.order_depths[product]
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            if best_bid >= best_ask:  # Invalid spread, skip
                continue
            mid_price = (best_bid + best_ask) / 2
            position = state.position.get(product, 0)
            position_limit = self.get_position_limit(product)
            spread = 2  # Fixed spread for simplicity
            bid_price = math.floor(mid_price - spread / 2)
            ask_price = math.ceil(mid_price + spread / 2)
            buy_size = min(10, position_limit - position)
            sell_size = min(10, position_limit + position)
            orders = []
            if buy_size > 0:
                orders.append(Order(product, bid_price, buy_size))
            if sell_size > 0:
                orders.append(Order(product, ask_price, -sell_size))
            if orders:
                result[product] = orders

        # Get current price of VOLCANIC_ROCK
        S = None
        rock_depth = state.order_depths.get(self.ROCK_PRODUCT)
        if rock_depth and rock_depth.buy_orders and rock_depth.sell_orders:
            best_bid = max(rock_depth.buy_orders.keys())
            best_ask = min(rock_depth.sell_orders.keys())
            S = (best_bid + best_ask) / 2

        # Update historical mid-prices for volatility calculation
        if S is not None:
            if "VOLCANIC_ROCK_mid_prices" not in trader_data:
                trader_data["VOLCANIC_ROCK_mid_prices"] = []
            trader_data["VOLCANIC_ROCK_mid_prices"].append(S)
            N = 100  # Maximum number of historical prices to store
            if len(trader_data["VOLCANIC_ROCK_mid_prices"]) > N:
                trader_data["VOLCANIC_ROCK_mid_prices"] = trader_data["VOLCANIC_ROCK_mid_prices"][-N:]

        # Estimate volatility (sigma)
        sigma = None
        if "VOLCANIC_ROCK_mid_prices" in trader_data and len(trader_data["VOLCANIC_ROCK_mid_prices"]) >= 10:
            prices = trader_data["VOLCANIC_ROCK_mid_prices"]
            log_returns = [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
            if len(log_returns) > 1:
                sigma = statistics.stdev(log_returns)
        if sigma is None and S is not None:
            # Fallback to implied volatility from ATM voucher
            atm_voucher = "VOLCANIC_ROCK_VOUCHER_10000"
            atm_depth = state.order_depths.get(atm_voucher)
            if atm_depth and atm_depth.buy_orders and atm_depth.sell_orders:
                C_market = (max(atm_depth.buy_orders.keys()) + min(atm_depth.sell_orders.keys())) / 2
                sigma = C_market / (0.4 * S * math.sqrt(self.T))  # Approximation: C ≈ 0.4 * S * σ * sqrt(T)
        if sigma is None or sigma <= 0:
            sigma = 0.1  # Default volatility if no better estimate

        if S is not None:
            # Options pricing, trading, and hedging
            for voucher, K in self.VOUCHERS:
                voucher_depth = state.order_depths.get(voucher)
                if not voucher_depth or not voucher_depth.buy_orders or not voucher_depth.sell_orders:
                    continue
                best_bid = max(voucher_depth.buy_orders.keys())
                best_ask = min(voucher_depth.sell_orders.keys())
                mid_price = (best_bid + best_ask) / 2
                C_theo = self.black_scholes_call(S, K, self.T, sigma)
                delta = self.black_scholes_delta(S, K, self.T, sigma)
                threshold = 10  # Mispricing threshold
                position = state.position.get(voucher, 0)
                position_limit = self.get_position_limit(voucher)
                orders = result.setdefault(voucher, [])
                rock_orders = result.setdefault(self.ROCK_PRODUCT, [])

                # Buy if underpriced
                if mid_price < C_theo - threshold and position < position_limit:
                    qty = min(10, abs(voucher_depth.sell_orders.get(best_ask, 0)),
                              position_limit - position)
                    if qty > 0:
                        orders.append(Order(voucher, best_ask, qty))
                        rock_qty = math.ceil(delta * qty)
                        if (rock_depth.buy_orders and
                            rock_qty <= self.get_position_limit(self.ROCK_PRODUCT) + state.position.get(self.ROCK_PRODUCT, 0)):
                            rock_orders.append(Order(self.ROCK_PRODUCT, max(rock_depth.buy_orders.keys()), -rock_qty))

                # Sell if overpriced
                elif mid_price > C_theo + threshold and position > -position_limit:
                    qty = min(10, voucher_depth.buy_orders.get(best_bid, 0),
                              position_limit + position)
                    if qty > 0:
                        orders.append(Order(voucher, best_bid, -qty))
                        rock_qty = math.ceil(delta * qty)
                        if (rock_depth.sell_orders and
                            rock_qty <= self.get_position_limit(self.ROCK_PRODUCT) - state.position.get(self.ROCK_PRODUCT, 0)):
                            rock_orders.append(Order(self.ROCK_PRODUCT, min(rock_depth.sell_orders.keys()), rock_qty))

            # Arbitrage: Voucher vs. Voucher
            for i, (voucher1, K1) in enumerate(self.VOUCHERS):
                for voucher2, K2 in self.VOUCHERS[i + 1:]:
                    if K1 >= K2:
                        continue
                    depth1 = state.order_depths.get(voucher1)
                    depth2 = state.order_depths.get(voucher2)
                    if not (depth1 and depth2 and depth1.sell_orders and depth2.buy_orders):
                        continue
                    ask1 = min(depth1.sell_orders.keys())
                    bid2 = max(depth2.buy_orders.keys())
                    if bid2 > ask1:  # Sell higher strike, buy lower strike
                        qty = min(
                            depth2.buy_orders[bid2],
                            abs(depth1.sell_orders[ask1]),
                            self.get_position_limit(voucher2) + state.position.get(voucher2, 0),
                            self.get_position_limit(voucher1) - state.position.get(voucher1, 0)
                        )
                        if qty > 0:
                            result.setdefault(voucher2, []).append(Order(voucher2, bid2, -qty))
                            result.setdefault(voucher1, []).append(Order(voucher1, ask1, qty))

            # Arbitrage: Voucher vs. Rock
            for voucher, _ in self.VOUCHERS:
                voucher_depth = state.order_depths.get(voucher)
                if not (voucher_depth and voucher_depth.buy_orders and rock_depth and rock_depth.sell_orders):
                    continue
                voucher_bid = max(voucher_depth.buy_orders.keys())
                rock_ask = min(rock_depth.sell_orders.keys())
                if voucher_bid > rock_ask:  # Sell voucher, buy rock
                    qty = min(
                        voucher_depth.buy_orders[voucher_bid],
                        abs(rock_depth.sell_orders[rock_ask]),
                        self.get_position_limit(voucher) + state.position.get(voucher, 0),
                        self.get_position_limit(self.ROCK_PRODUCT) - state.position.get(self.ROCK_PRODUCT, 0)
                    )
                    if qty > 0:
                        result.setdefault(voucher, []).append(Order(voucher, voucher_bid, -qty))
                        result.setdefault(self.ROCK_PRODUCT, []).append(Order(self.ROCK_PRODUCT, rock_ask, qty))

        # Serialize trader data and return
        traderData = json.dumps(trader_data)
        conversions = 0
        return result, conversions, traderData