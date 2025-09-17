# momentum_indicator.py
from typing import List, Optional

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculates the Relative Strength Index (RSI) for a given list of prices.
    """
    if len(prices) < period + 1:
        return None  # Not enough data to calculate RSI

    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    gains = [change for change in changes if change > 0]
    losses = [-change for change in changes if change < 0]

    # Calculate initial average gain and loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        return 100.0 # Avoid division by zero; price is only going up

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_momentum_score(
    volume_divergence: float,
    persistence_count: int,
    rsi_value: int,
    dominant_dex_has_lower_price: bool
) -> (float, str):
    """
    Calculates a momentum score for a cryptocurrency based on arbitrage signals.

    Args:
        volume_divergence (float): The ratio of trading volume between two DEXs.
                                   (e.g., 2.5 means one DEX has 2.5x the volume of the other).
        persistence_count (int): The number of times the opportunity has been detected recently.
        rsi_value (int): The Relative Strength Index (RSI) value of the asset.
        dominant_dex_has_lower_price (bool): True if the DEX with higher volume has the lower price.

    Returns:
        A tuple containing:
        - The calculated momentum score (0-10).
        - A brief, human-readable interpretation of the score.
    """
    # 1. Determine Momentum Direction
    # If the DEX with more volume has the lower price, it suggests a potential upward trend,
    # as smart money might be accumulating there before the price corrects upwards.
    # Conversely, if the dominant DEX has a higher price, it could signal a downward trend
    # as traders might be selling off there.
    direction = "Upward" if dominant_dex_has_lower_price else "Downward"

    # 2. Calculate Base Score (out of 8 points)
    # Normalize volume divergence (clamping at a max of 5x for scoring)
    volume_score = min(volume_divergence, 5.0)  # Max score contribution from volume is 5

    # Normalize persistence count (clamping at a max of 5 detections)
    persistence_score = min(persistence_count, 5) # Max score contribution from persistence is 5

    # Weight the scores. We'll consider volume divergence slightly more important.
    # Max possible base score is (3 * 5/5) + (5 * 5/5) = 8
    base_score = (0.6 * persistence_score) + (1.0 * volume_score)

    # 3. Apply RSI Adjustment (+/- 2 points)
    rsi_adjustment = 0
    if direction == "Upward":
        if rsi_value < 30:
            rsi_adjustment = 2.0  # Bonus: Strong buy signal (oversold)
        elif rsi_value > 70:
            rsi_adjustment = -2.0 # Penalty: Potential reversal (overbought)
    
    elif direction == "Downward":
        if rsi_value > 70:
            rsi_adjustment = 2.0  # Bonus: Strong sell signal (overbought)
        elif rsi_value < 30:
            rsi_adjustment = -2.0 # Penalty: Potential reversal (oversold)

    # 4. Calculate Final Score
    final_score = base_score + rsi_adjustment
    
    # Clamp the final score to a 0-10 scale
    final_score = max(0, min(final_score, 10))

    # 5. Generate Interpretation
    interpretation = f"Score: {final_score:.1f}/10 - "
    if final_score >= 8:
        interpretation += f"Very High {direction} Momentum. Potential strong signal."
    elif final_score >= 6:
        interpretation += f"High {direction} Momentum. Worth monitoring."
    elif final_score >= 4:
        interpretation += f"Moderate {direction} Momentum."
    elif final_score >= 2:
        interpretation += f"Low {direction} Momentum."
    else:
        interpretation += f"Negligible {direction} Momentum."

    return final_score, interpretation

# --- Example Usage ---
if __name__ == "__main__":
    print("--- Cryptocurrency Momentum Indicator Examples ---")

    # Example 1: Strong upward signal
    # High volume on the cheaper DEX, seen multiple times, and the token is oversold.
    score1, interp1 = calculate_momentum_score(
        volume_divergence=3.5,
        persistence_count=4,
        rsi_value=25,
        dominant_dex_has_lower_price=True
    )
    print(f"\nExample 1 (Strong Upward):")
    print(f"Inputs: Vol Divergence=3.5x, Persistence=4, RSI=25, Cheaper DEX is Dominant=True")
    print(f"Output: {interp1}")

    # Example 2: Moderate upward signal, but RSI is high
    # Decent volume and persistence, but the token is overbought, reducing the score.
    score2, interp2 = calculate_momentum_score(
        volume_divergence=3.0,
        persistence_count=3,
        rsi_value=75,
        dominant_dex_has_lower_price=True
    )
    print(f"\nExample 2 (Upward, High RSI):")
    print(f"Inputs: Vol Divergence=3.0x, Persistence=3, RSI=75, Cheaper DEX is Dominant=True")
    print(f"Output: {interp2}")

    # Example 3: Strong downward signal
    # High volume on the more expensive DEX, seen multiple times, and the token is overbought.
    score3, interp3 = calculate_momentum_score(
        volume_divergence=4.0,
        persistence_count=5,
        rsi_value=80,
        dominant_dex_has_lower_price=False
    )
    print(f"\nExample 3 (Strong Downward):")
    print(f"Inputs: Vol Divergence=4.0x, Persistence=5, RSI=80, Cheaper DEX is Dominant=False")
    print(f"Output: {interp3}")

    # Example 4: Weak signal
    # Low volume divergence and persistence, neutral RSI.
    score4, interp4 = calculate_momentum_score(
        volume_divergence=1.2,
        persistence_count=1,
        rsi_value=50,
        dominant_dex_has_lower_price=True
    )
    print(f"\nExample 4 (Weak Signal):")
    print(f"Inputs: Vol Divergence=1.2x, Persistence=1, RSI=50, Cheaper DEX is Dominant=True")
    print(f"Output: {interp4}")


# --- Future Improvement Suggestions ---
# 1. Real-Time API Integration:
#    - This function could be integrated into the main `ArbitrageScanner`.
#    - The scanner would need to be modified to track opportunity persistence (e.g., how many
#      times the same opportunity appears in a 10-minute window).
#    - It would also need to fetch the trading volume for each side of the pair to calculate
#      the `volume_divergence` and fetch the RSI from an API like CoinGecko or a technical
#      analysis library.

# 2. Backtesting Framework:
#    - To validate the effectiveness of this indicator, a backtesting script could be developed.
#    - This script would run the indicator on historical price and volume data to simulate trades
#      and evaluate its profitability and accuracy over time.

# 3. Multi-Factor Model:
#    - The indicator could be enhanced by adding more data points to the scoring model.
#    - Examples include: social media sentiment (e.g., from Twitter/X), developer activity
#      on GitHub, or other technical indicators like MACD or Bollinger Bands. This would
#      create a more holistic and potentially more accurate signal.