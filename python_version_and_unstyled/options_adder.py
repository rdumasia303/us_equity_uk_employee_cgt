import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
from calculate_vest_price import VestPriceCalculator
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptionsProcessor:
    def __init__(self, stock_file: str, forex_file: str, holidays_file: str):
        self.price_calculator = VestPriceCalculator(
            stock_file=stock_file,
            forex_file=forex_file,
            holidays_file=holidays_file
        )
        self.records = []
        
    def get_user_input(self) -> tuple:
        """Get option exercise details from user."""
        current_grant = None
        
        while True:
            if not current_grant:
                current_grant = input("Enter Grant ID (e.g., N1234): ").strip()
            else:
                print(f"Using Grant ID: {current_grant}")
            
            while True:
                date = input("Enter exercise date (YYYY-MM-DD): ").strip()
                try:
                    datetime.strptime(date, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD")
            
            while True:
                try:
                    price = float(input("Enter exercise price in USD: ").strip())
                    break
                except ValueError:
                    print("Invalid price. Please enter a number")
            
            while True:
                try:
                    quantity = int(input("Enter number of options exercised (net): ").strip())
                    break
                except ValueError:
                    print("Invalid quantity. Please enter a whole number")
            
            # Get currency conversion for the date
            _, fx_rate, gbp_price, actual_date = self.price_calculator.get_vest_price(date)
            
            if fx_rate is None:
                logger.error(f"Could not get exchange rate for date {date}")
                if not self._confirm("Exchange rate not found. Continue anyway?"):
                    continue
                fx_rate = 0
                gbp_price = 0
            
            # Create the record
            record = {
                'Record Type': 'Buy',
                'Date': date,
                'Qty.': quantity,
                'Price Per Share': price,
                'Price Per Share GBP': price / fx_rate if fx_rate else None,
                'Exchange Rate': fx_rate,
                'Order Type': 'Exercise',
                'Type': 'Non-Qualified Stock Option',
                'Grant Number': current_grant
            }
            
            self.records.append(record)
            
            if not self._confirm("Add another exercise for the same grant?"):
                if not self._confirm("Add exercises for a different grant?"):
                    break
                current_grant = None
    
    def _confirm(self, question: str) -> bool:
        """Get yes/no confirmation from user."""
        while True:
            response = input(f"{question} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            if response in ['n', 'no']:
                return False
            print("Please answer 'y' or 'n'")
    
    def save_to_csv(self, output_file: str):
        """Save records to CSV file."""
        if not self.records:
            logger.warning("No records to save")
            return
        
        df = pd.DataFrame(self.records)
        df.to_csv(output_file, index=False)
        logger.info(f"Saved {len(self.records)} records to {output_file}")
        
        # Show preview
        print("\nSaved records preview:")
        print(df.to_string())

def main():
    processor = OptionsProcessor(
        stock_file="roku_stock_prices.csv",
        forex_file="gbpusd_rates.csv",
        holidays_file="us_holidays.json"
    )
    
    print("Options Exercise Processor")
    print("=========================")
    print("This tool will help you record option exercises.")
    print("Please have the following information ready:")
    print("- Grant ID")
    print("- Exercise date")
    print("- Exercise price (USD)")
    print("- Number of options exercised (net of withholding)")
    print("=========================\n")
    
    try:
        processor.get_user_input()
        
        if processor.records:
            output_file = "option_exercises.csv"
            processor.save_to_csv(output_file)
            print(f"\nData has been saved to {output_file}")
            print("You can now combine this with your other transaction data.")
        else:
            print("\nNo records were created.")
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()