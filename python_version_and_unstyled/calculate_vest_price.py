import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VestPriceCalculator:
    """Calculate vest prices in GBP considering holidays and weekend dates."""
    
    def __init__(self, stock_file: str, forex_file: str, holidays_file: str):
        """
        Initialize with data files.
        
        Args:
            stock_file: CSV file with stock prices (Date, Close_Price)
            forex_file: CSV file with BOE USD/GBP rates
            holidays_file: JSON file with US holidays
        """
        self.stock_prices = self._load_stock_prices(stock_file)
        self.forex_rates = self._load_forex_rates(forex_file)
        self.holidays = self._load_holidays(holidays_file)
        
    def _load_stock_prices(self, file_path: str) -> dict:
        """Load and index stock prices by date."""
        df = pd.read_csv(file_path)
        # Convert dates to YYYY-MM-DD string format for consistent lookup
        prices = {}
        for _, row in df.iterrows():
            date_str = pd.to_datetime(row['Date']).strftime('%Y-%m-%d')
            prices[date_str] = float(row['Close_Price'])
            
        # Log some diagnostic information
        logger.info(f"Loaded {len(prices)} stock prices")
        logger.info(f"Date range: {min(prices.keys())} to {max(prices.keys())}")
        logger.info(f"Sample dates: {list(sorted(prices.keys()))[:5]}")
        return prices
    
    def _load_forex_rates(self, file_path: str) -> dict:
        """Load and parse forex rates from CSV."""
        rates = {}
        try:
            df = pd.read_csv(file_path)
            # Convert DataFrame to dictionary with dates as keys
            rates = df.set_index('Date')['Average'].to_dict()
            
            logger.info(f"Loaded {len(rates)} forex rates from {file_path}")
            logger.info(f"Date range: {min(rates.keys())} to {max(rates.keys())}")
            return rates
            
        except Exception as e:
            logger.error(f"Error loading forex rates: {str(e)}")
            raise
    
    def _load_holidays(self, file_path: str) -> set:
        """Load US holiday dates from JSON file."""
        with open(file_path, 'r') as f:
            holiday_data = json.load(f)
        return {holiday['date'] for holiday in holiday_data 
                if holiday['global'] or 'Optional' not in holiday['types']}
    
    def _is_business_day(self, date: datetime) -> bool:
        """Check if given date is a business day."""
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        return date.strftime('%Y-%m-%d') not in self.holidays
    
    def _get_next_business_day(self, date: datetime) -> datetime:
        """Get the next business day from given date."""
        next_day = date
        while not self._is_business_day(next_day):
            next_day += timedelta(days=1)
        return next_day
    
    def get_vest_price(self, vest_date: str) -> Tuple[Optional[float], Optional[float], Optional[float], str]:
        """
        Get stock price and GBP conversion for a vest date.
        
        Args:
            vest_date: Date string in YYYY-MM-DD format
            
        Returns:
            Tuple of (USD price, GBP/USD rate, GBP price, actual_date)
        """
        try:
            # Convert vest date to datetime
            date = datetime.strptime(vest_date, '%Y-%m-%d')

            print(f"Checking vest date: {vest_date}")
            
            # Get next business day if needed
            actual_date = self._get_next_business_day(date)

            print(f"Actual date: {actual_date.strftime('%Y-%m-%d')}")
            actual_date_str = actual_date.strftime('%Y-%m-%d')
            
            # Get stock price
            usd_price = self.stock_prices.get(actual_date_str)
            if usd_price is None:
                logger.warning(f"No stock price found for {actual_date_str}")
                logger.debug(f"Available dates near requested date:")
                # Show nearby dates for debugging
                nearby_dates = [d for d in self.stock_prices.keys() 
                              if abs((datetime.strptime(d, '%Y-%m-%d') - 
                                    datetime.strptime(actual_date_str, '%Y-%m-%d')).days) <= 5]
                if nearby_dates:
                    logger.debug(f"Nearby dates in data: {sorted(nearby_dates)}")
                return None, None, None, actual_date_str
            
            # Get forex rate
            gbp_usd_rate = self.forex_rates.get(actual_date_str)
            if gbp_usd_rate is None:
                logger.warning(f"No forex rate found for {actual_date_str}")
                return usd_price, None, None, actual_date_str
            
            # Calculate GBP price
            gbp_price = usd_price / gbp_usd_rate
            
            return usd_price, gbp_usd_rate, gbp_price, actual_date_str
            
        except Exception as e:
            logger.error(f"Error calculating vest price for {vest_date}: {str(e)}")
            return None, None, None, vest_date

def main():
    """Example usage of the VestPriceCalculator."""
    calculator = VestPriceCalculator(
        stock_file='roku_stock_prices.csv',
        forex_file='gbp_usd_rates.csv',
        holidays_file='us_holidays.json'
    )
    
    # Example dates to test
    test_dates = [
        '2024-01-01',  # New Year's Day
        '2024-01-13',  # Saturday
        '2024-01-14',  # Sunday
        '2024-09-01',  # MLK Day
        '2024-01-16',  # Regular business day
    ]
    
    print("\nTesting vest price calculations:")
    print(f"{'Vest Date':<12} {'Actual Date':<12} {'USD Price':>10} {'GBP/USD':>10} {'GBP Price':>10}")
    print("-" * 60)
    
    for date in test_dates:
        usd_price, fx_rate, gbp_price, actual_date = calculator.get_vest_price(date)
        print(f"{date:<12} {actual_date:<12} "
              f"{usd_price:>10.2f} {fx_rate:>10.4f} {gbp_price:>10.2f}"
              if all(v is not None for v in (usd_price, fx_rate, gbp_price))
              else f"{date:<12} {actual_date:<12} {'N/A':>10} {'N/A':>10} {'N/A':>10}")

if __name__ == "__main__":
    main()