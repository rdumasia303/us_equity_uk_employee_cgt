import argparse
import sys
import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_stock_data(symbol: str, start_date: str, end_date: str, output_file: str) -> None:
    """
    Download historical stock data from Yahoo Finance and save to CSV.
    Ensures dates are in YYYY-MM-DD format.
    
    Args:
        symbol: Stock symbol (e.g., 'MSFT')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_file: Path to save the CSV file
    """
    try:
        # Validate date formats
        try:
            pd.to_datetime(start_date).strftime('%Y-%m-%d')
            pd.to_datetime(end_date).strftime('%Y-%m-%d')
        except ValueError as e:
            raise ValueError(f"Dates must be in YYYY-MM-DD format: {str(e)}")

        logger.info(f"Downloading {symbol} data from {start_date} to {end_date}")
        
        # Add one day to end_date to ensure we include the end date in the results
        end = pd.to_datetime(end_date) + timedelta(days=1)
        stock = yf.Ticker(symbol)
        hist = stock.history(start=start_date, end=end)
        
        if hist.empty:
            raise ValueError(f"No data returned for {symbol} between {start_date} and {end_date}")
        
        # Keep only the Date and Close price
        hist = hist[['Close']].round(6)
        
        # Reset index to make Date a column and ensure YYYY-MM-DD format
        hist.reset_index(inplace=True)
        hist['Date'] = pd.to_datetime(hist['Date']).dt.strftime('%Y-%m-%d')
        
        # Rename columns for clarity
        hist.columns = ['Date', 'Close_Price']
        
        # Remove any potential duplicates
        hist = hist.drop_duplicates(subset=['Date'], keep='first')
        
        # Save to CSV
        hist.to_csv(output_file, index=False)
        logger.info(f"Data saved to {output_file}")
        
        # Show sample and date range
        logger.info("\nFirst few rows of downloaded data:")
        logger.info(hist.head().to_string())
        logger.info(f"\nDate range: {hist['Date'].min()} to {hist['Date'].max()}")
        logger.info(f"Total trading days: {len(hist)}")
        
    except Exception as e:
        logger.error(f"Error downloading stock data: {str(e)}")
        raise


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download stock data for a given stock symbol starting from a specified date.",
        epilog="Example usage: python your_script.py AAPL 2023-01-01"
    )
    
    parser.add_argument(
        'stock_symbol',
        type=str,
        help='The stock symbol (e.g., AAPL for Apple Inc.).'
    )
    
    parser.add_argument(
        'start_date',
        type=str,
        help='The start date in YYYY-MM-DD format.'
    )
    
    return parser.parse_args()

def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Incorrect date format for '{date_text}'. Expected format: YYYY-MM-DD.")
        sys.exit(1)

def main(stock_symbol, start_date):
    # Define end_date as 30 days from the current date
    end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') 
    
    output_file = f"{stock_symbol}_stock_prices.csv"
    
    # Call the download_stock_data function with the provided arguments
    download_stock_data(stock_symbol, start_date, end_date, output_file)
    
    print(f"Data successfully downloaded to {output_file}")

if __name__ == "__main__":
    args = parse_arguments()
    validate_date(args.start_date)
    main(args.stock_symbol, args.start_date)
