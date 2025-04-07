import json

# Conversion rates extracted from the image
# rates[from_currency][to_currency] = amount of to_currency for 1 unit of from_currency
rates = {
    'Snowballs': {'Snowballs': 1.0, 'Pizzas': 1.45, 'Silicon Nuggets': 0.52, 'SeaShells': 0.72},
    'Pizzas': {'Snowballs': 0.7, 'Pizzas': 1.0, 'Silicon Nuggets': 0.31, 'SeaShells': 0.48},
    'Silicon Nuggets': {'Snowballs': 1.95, 'Pizzas': 3.1, 'Silicon Nuggets': 1.0, 'SeaShells': 1.49},
    'SeaShells': {'Snowballs': 1.34, 'Pizzas': 1.98, 'Silicon Nuggets': 0.64, 'SeaShells': 1.0}
}

currencies = list(rates.keys())
start_currency = 'SeaShells'
initial_amount = 2000.0
max_trades = 20 # Set a maximum number of trades to explore

# List to store results: (final_factor, path_list)
results = []

def find_best_paths(current_currency, current_factor, current_path):
    """
    Recursively explores trading paths using DFS.

    Args:
        current_currency (str): The currency currently held.
        current_factor (float): The cumulative conversion factor from the start.
        current_path (list): The list of currencies visited so far.
    """
    num_trades = len(current_path) - 1

    # --- Base Cases ---
    # 1. If we returned to SeaShells (and made at least one trade)
    if current_currency == start_currency and num_trades > 0:
        results.append((current_factor, current_path))
        # Optional: Allow further exploration from SeaShells if desired,
        # but stop if we hit max_trades depth anyway in the next check.

    # 2. If we exceed the maximum number of trades allowed
    if num_trades >= max_trades:
        return # Stop exploring this path

    # --- Recursive Step ---
    # Explore converting to every other currency
    for next_currency in currencies:
        if next_currency in rates[current_currency]:
            conversion_rate = rates[current_currency][next_currency]
            if conversion_rate > 0: # Ensure there's a valid conversion
                new_factor = current_factor * conversion_rate
                new_path = current_path + [next_currency]
                find_best_paths(next_currency, new_factor, new_path)

# --- Main Execution ---
print(f"Starting analysis with {initial_amount} {start_currency}, max trades: {max_trades}\n")

# Start the recursive search from SeaShells with an initial factor of 1.0
find_best_paths(start_currency, 1.0, [start_currency])

# --- Process Results ---
if not results:
    print("No valid trading paths found ending back in SeaShells.")
else:
    # Sort results by the final factor (descending)
    results.sort(key=lambda x: x[0], reverse=True)

    print("--- Potential Trading Paths Found ---")
    for factor, path in results:
        final_amount = initial_amount * factor
        num_trades_actual = len(path) - 1
        path_str = " -> ".join(path)
        print(f"Path ({num_trades_actual} trades): {path_str}")
        print(f"  Factor: {factor:.4f}")
        print(f"  Final Amount: {final_amount:.4f} SeaShells")
        print("-" * 10)

    # Find the best result
    best_factor, best_path = results[0]
    best_final_amount = initial_amount * best_factor
    best_num_trades = len(best_path) - 1

    print("\n--- Best Path Found ---")
    print(f"Path: {' -> '.join(best_path)}")
    print(f"Number of Trades: {best_num_trades}")
    print(f"Overall Conversion Factor: {best_factor:.4f}")
    print(f"Starting Amount: {initial_amount:.4f} SeaShells")
    print(f"Best Final Amount: {best_final_amount:.4f} SeaShells")
    print(f"Profit/Loss: {best_final_amount - initial_amount:.4f} SeaShells")