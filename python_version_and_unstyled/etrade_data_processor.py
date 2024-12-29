import pandas as pd
import numpy as np
from datetime import datetime
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict

from calculate_vest_price import VestPriceCalculator

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for data validation errors."""
    pass

class ETradeDataProcessor:
    """Process and consolidate ETrade gains/losses and benefits data."""
    
    def __init__(self, stock_file: str, forex_file: str, holidays_file: str):
        self.gains_columns = [
            "Record Type",
            "Date Acquired",
            "Date Sold",
            "Qty.",
            "Proceeds Per Share",
            "Vest Date",
            "Vest Date FMV",
            "Grant Date FMV",
            "Grant Number",
            "Order Type",
            "Type",
        ]
        
        self.date_columns = ["Date Acquired", "Date Sold", "Vest Date"]
        
        # Track validation statistics
        self.validation_stats = {
            'unmatched_vests': 0,
            'missing_fmv': 0,
            'negative_quantities': 0,
            'zero_prices': 0,
            'calculated_prices': 0
        }
        
        # Initialize price calculator
        self.price_calculator = VestPriceCalculator(
            stock_file=stock_file,
            forex_file=forex_file,
            holidays_file=holidays_file
        )
    
    def _validate_required_columns(self, df: pd.DataFrame, required_columns: list, context: str) -> None:
        """Validate that all required columns are present."""
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValidationError(
                f"Missing required columns in {context}: {', '.join(missing_columns)}"
            )

    def _validate_numeric_values(self, df: pd.DataFrame) -> None:
        """Validate numeric values in the DataFrame."""
        # Check for negative quantities
        neg_qty = df[df['Qty.'] < 0]
        if not neg_qty.empty:
            self.validation_stats['negative_quantities'] += len(neg_qty)
            logger.warning(f"Found {len(neg_qty)} records with negative quantities:")
            logger.warning(neg_qty[['Date', 'Grant Number', 'Qty.']].to_string())

        # Check for zero or negative prices
        if 'Price Per Share' in df.columns:
            zero_prices = df[df['Price Per Share'] <= 0]
            if not zero_prices.empty:
                self.validation_stats['zero_prices'] += len(zero_prices)
                logger.warning(f"Found {len(zero_prices)} records with zero or negative prices:")
                logger.warning(zero_prices[['Date', 'Grant Number', 'Price Per Share']].to_string())

    def _standardize_dates(self, df: pd.DataFrame, date_columns: list) -> pd.DataFrame:
        """Convert date columns to ISO 8601 format."""
        for col in date_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
                    # Check for any dates that couldn't be parsed
                    null_dates = df[df[col].isna()]
                    if not null_dates.empty:
                        logger.warning(f"Found {len(null_dates)} unparseable dates in {col}")
                except Exception as e:
                    logger.error(f"Error processing dates in column {col}: {str(e)}")
                    raise
        return df

    def _calculate_weighted_average(self, group: pd.DataFrame) -> float:
        """Calculate weighted average price for a group of transactions."""
        if group['Qty.'].sum() == 0:
            logger.warning("Attempting to calculate weighted average with zero total quantity")
            return 0
        return (group['Price Per Share'] * group['Qty.']).sum() / group['Qty.'].sum()

    def process_gains_losses(self, file_path: str) -> pd.DataFrame:
        """
        Process ETrade gains and losses Excel file with validation.
        
        Args:
            file_path: Path to the gains/losses Excel file
            
        Returns:
            Processed DataFrame
        """
        logger.info(f"Processing gains/losses file: {file_path}")
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Gains/losses file not found: {file_path}")
                
            df = pd.read_excel(
                file_path,
                usecols=self.gains_columns,
                skiprows=[1]
            )
            
            # Validate required columns
            self._validate_required_columns(df, self.gains_columns, "gains/losses file")
            
            # Standardize dates
            df = self._standardize_dates(df, self.date_columns)
            
            # Validate numeric values
            self._validate_numeric_values(df)
            
            logger.info(f"Successfully processed gains/losses data with {len(df)} records")
            return df
            
        except Exception as e:
            logger.error(f"Error processing gains/losses file: {str(e)}")
            raise

    def process_benefits(self, file_path: str) -> pd.DataFrame:
        """
        Process ETrade benefits Excel file with validation.
        
        Args:
            file_path: Path to the benefits Excel file
            
        Returns:
            Processed DataFrame with vesting information
        """
        logger.info(f"Processing benefits file: {file_path}")
        required_columns = ['Grant Number', 'Date', 'Event Type', 'Qty. or Amount']
        
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Benefits file not found: {file_path}")
                
            df = pd.read_excel(file_path)
            
            # Validate required columns
            self._validate_required_columns(df, required_columns, "benefits file")
            
            # Convert date format
            df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce').dt.strftime('%Y-%m-%d')
            
            # Validate dates
            if df['Date'].isna().any():
                logger.warning(f"Found {df['Date'].isna().sum()} invalid dates in benefits file")
            
            # Convert quantity column to integer and validate
            df["Qty. or Amount"] = pd.to_numeric(df["Qty. or Amount"], errors='coerce').fillna(0).astype(int)
            
            # Filter for vested shares
            filtered_df = df[
                (df['Event Type'] == 'Shares released')
            ][['Grant Number', 'Date', 'Event Type', 'Qty. or Amount']]
            
            if filtered_df.empty:
                logger.warning("No 'Shares released' events found in benefits file")
            
            logger.info(f"Successfully processed benefits data: {len(filtered_df)} vesting events found")
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error processing benefits file: {str(e)}")
            raise

    def consolidate_similar_prices(self, df: pd.DataFrame, price_tolerance: float = 0.01) -> pd.DataFrame:
        """
        Consolidate sales with similar prices on the same day.
        
        Args:
            df: DataFrame containing transaction records
            price_tolerance: Maximum percentage difference in price to be considered "similar"
            
        Returns:
            DataFrame with consolidated transactions
        """
        result_rows = []
        consolidation_stats = {'total_consolidated': 0, 'groups_consolidated': 0}
        
        # Group by date and type
        for (date, record_type, order_type, security_type), group in df.groupby([
            'Date', 'Record Type', 'Order Type', 'Type'
        ]):
            if record_type == 'Buy':
                # Don't consolidate buys
                result_rows.extend(group.to_dict('records'))
                continue
                
            # Process sells with similar prices
            while len(group) > 0:
                ref_price = group.iloc[0]['Price Per Share']
                
                # Find similar prices
                similar_prices = group[
                    (group['Price Per Share'] >= ref_price * (1 - price_tolerance)) &
                    (group['Price Per Share'] <= ref_price * (1 + price_tolerance))
                ]
                
                if len(similar_prices) > 1:  # Only count as consolidation if multiple records were combined
                    consolidation_stats['total_consolidated'] += len(similar_prices)
                    consolidation_stats['groups_consolidated'] += 1
                    
                    # Calculate weighted averages for both USD and GBP
                    avg_price_usd = self._calculate_weighted_average(similar_prices)
                    
                    # Calculate weighted average GBP price if available
                    if 'Price Per Share GBP' in similar_prices.columns and not similar_prices['Price Per Share GBP'].isna().all():
                        avg_price_gbp = self._calculate_weighted_average(
                            similar_prices[~similar_prices['Price Per Share GBP'].isna()].assign(
                                **{'Price Per Share': similar_prices['Price Per Share GBP']}
                            )
                        )
                        # Use the most common exchange rate
                        exchange_rate = similar_prices['Exchange Rate'].mode().iloc[0]
                    else:
                        avg_price_gbp = None
                        exchange_rate = None
                    
                    total_qty = similar_prices['Qty.'].sum()
                    
                    # Combine grant numbers
                    combined_grants = '-'.join(sorted(set(
                        grant
                        for grants in similar_prices['Grant Number']
                        for grant in grants.split('-')
                    )))
                    
                    # Create consolidated record
                    result_rows.append({
                        'Date': date,
                        'Record Type': record_type,
                        'Order Type': order_type,
                        'Type': security_type,
                        'Qty.': total_qty,
                        'Price Per Share': round(avg_price_usd, 6),
                        'Price Per Share GBP': round(avg_price_gbp, 6) if avg_price_gbp is not None else None,
                        'Exchange Rate': exchange_rate,
                        'Grant Number': combined_grants
                    })
                    
                    group = group.drop(similar_prices.index)
                else:
                    result_rows.append(group.iloc[0].to_dict())
                    group = group.iloc[1:]
        
        logger.info(f"Price consolidation stats: {consolidation_stats}")
        return pd.DataFrame(result_rows)

    def consolidate_transactions(self, sales_df: pd.DataFrame, vests_df: pd.DataFrame) -> pd.DataFrame:
        """
        Combine sales and vesting data into consolidated transaction records.
        
        Args:
            sales_df: Processed sales/gains DataFrame
            vests_df: Processed vesting/benefits DataFrame
            
        Returns:
            Consolidated DataFrame with all transactions
        """
        # First try to get FMV from sales data
        fmv_mapping = sales_df[['Grant Number', 'Vest Date', 'Vest Date FMV']].drop_duplicates()
        
        # Check for multiple FMV values for same grant/date combination
        fmv_duplicates = fmv_mapping.groupby(['Grant Number', 'Vest Date']).size()
        fmv_duplicates = fmv_duplicates[fmv_duplicates > 1]
        if not fmv_duplicates.empty:
            logger.warning("Found multiple FMV values for same grant/date combinations:")
            logger.warning(fmv_duplicates.to_string())
        
        # Merge vesting data with FMV mapping
        vests_with_fmv = pd.merge(
            vests_df,
            fmv_mapping,
            left_on=['Grant Number', 'Date'],
            right_on=['Grant Number', 'Vest Date'],
            how='left'
        )
        
        # Calculate GBP prices for ALL vests
        logger.info(f"Converting {len(vests_with_fmv)} vest prices to GBP")
        
        for idx, row in vests_with_fmv.iterrows():
            # For records with missing FMV, calculate both USD and GBP
            if pd.isna(row['Vest Date FMV']):
                usd_price, fx_rate, gbp_price, actual_date = self.price_calculator.get_vest_price(row['Date'])
                if usd_price is not None:
                    vests_with_fmv.loc[idx, 'Vest Date FMV'] = usd_price
                    vests_with_fmv.loc[idx, 'GBP_Price'] = gbp_price
                    vests_with_fmv.loc[idx, 'USD_GBP_Rate'] = fx_rate
                    vests_with_fmv.loc[idx, 'Actual_Vest_Date'] = actual_date
                    self.validation_stats['calculated_prices'] += 1
                else:
                    logger.warning(
                        f"Could not calculate price for vest on {row['Date']} "
                        f"(Grant: {row['Grant Number']})"
                    )
                    self.validation_stats['missing_fmv'] += 1
            # For records with FMV, just calculate GBP
            else:
                _, fx_rate, gbp_price, actual_date = self.price_calculator.get_vest_price(row['Date'])
                if fx_rate is not None:
                    vests_with_fmv.loc[idx, 'GBP_Price'] = row['Vest Date FMV'] / fx_rate
                    vests_with_fmv.loc[idx, 'USD_GBP_Rate'] = fx_rate
                    vests_with_fmv.loc[idx, 'Actual_Vest_Date'] = actual_date
        
        # Log date adjustments
        date_adjustments = vests_with_fmv[vests_with_fmv['Date'] != vests_with_fmv['Actual_Vest_Date']]
        if not date_adjustments.empty:
            logger.info(f"Adjusted {len(date_adjustments)} vest dates due to holidays/weekends:")
            for _, row in date_adjustments.iterrows():
                logger.info(
                    f"Grant {row['Grant Number']}: {row['Date']} → {row['Actual_Vest_Date']}"
                )
        
        # Check for unmatched vests
        unmatched_vests = vests_with_fmv[vests_with_fmv['Vest Date FMV'].isna()]
        if not unmatched_vests.empty:
            self.validation_stats['unmatched_vests'] += len(unmatched_vests)
            logger.warning(f"Found {len(unmatched_vests)} vests without matching FMV values:")
            logger.warning(unmatched_vests[['Grant Number', 'Date', 'Qty. or Amount']].to_string())
        
        # Convert vests to buy transactions
        buy_records = pd.DataFrame({
            'Record Type': 'Buy',
            'Qty.': vests_with_fmv['Qty. or Amount'],
            'Date': vests_with_fmv['Actual_Vest_Date'],  # Using actual vest date instead of original
            'Price Per Share': vests_with_fmv['Vest Date FMV'],
            'Price Per Share GBP': vests_with_fmv['GBP_Price'],
            'Exchange Rate': vests_with_fmv['USD_GBP_Rate'],
            'Order Type': 'Vest',
            'Type': 'Restricted Stock Unit',
            'Grant Number': vests_with_fmv['Grant Number']
        })
        
        # Format sell transactions and convert to GBP
        sell_records = pd.DataFrame({
            'Record Type': 'Sell',
            'Qty.': sales_df['Qty.'],
            'Date': sales_df['Date Sold'],
            'Price Per Share': sales_df['Proceeds Per Share'],
            'Order Type': sales_df['Order Type'],
            'Type': sales_df['Type'],
            'Grant Number': sales_df['Grant Number']
        })
        
        # Convert sell records to GBP
        logger.info(f"Converting {len(sell_records)} sell transactions to GBP")
        for idx, row in sell_records.iterrows():
            # Use the same price calculator that worked for buys
            _, fx_rate, _, actual_date = self.price_calculator.get_vest_price(row['Date'])
            if fx_rate is not None:
                sell_records.loc[idx, 'Price Per Share GBP'] = row['Price Per Share'] / fx_rate
                sell_records.loc[idx, 'Exchange Rate'] = fx_rate
            else:
                logger.warning(f"Could not find exchange rate for sell transaction on {row['Date']}")
        
        # Combine and process records
        all_records = pd.concat([buy_records, sell_records], ignore_index=True)
        all_records['Date'] = pd.to_datetime(all_records['Date'])
        
        # Consolidate similar prices and sort
        consolidated = self.consolidate_similar_prices(all_records)
        consolidated = consolidated.sort_values('Date').reset_index(drop=True)
        
        # Format date for output
        consolidated['Date'] = consolidated['Date'].dt.strftime('%Y-%m-%d')
        
        # Arrange columns
        final_columns = [
            'Record Type',
            'Date',
            'Qty.',
            'Price Per Share',
            'Price Per Share GBP',
            'Exchange Rate',
            'Order Type',
            'Type',
            'Grant Number'
        ]
        
        return consolidated[final_columns]

    def generate_validation_report(self) -> str:
        """Generate a summary report of all validation issues."""
        report = ["Validation Report:"]
        report.append(f"- Unmatched vests: {self.validation_stats['unmatched_vests']}")
        report.append(f"- Records with missing FMV: {self.validation_stats['missing_fmv']}")
        report.append(f"- Records with negative quantities: {self.validation_stats['negative_quantities']}")
        report.append(f"- Records with zero/negative prices: {self.validation_stats['zero_prices']}")
        return "\n".join(report)

def main():
    """Main execution function."""
    processor = ETradeDataProcessor(
        stock_file="roku_stock_prices.csv",
        forex_file="gbpusd_rates.csv",
        holidays_file="us_holidays.json"
    )
    
    try:
        # Process input files
        gains_df = processor.process_gains_losses("original_data/gainloss.xlsx")
        benefits_df = processor.process_benefits("original_data/benefit.xlsx")
        
        # Consolidate transactions
        result = processor.consolidate_transactions(gains_df, benefits_df)
        
        # Save output
        output_path = "output/consolidated_transactions.csv"
        result.to_csv(output_path, index=False)
        
        logger.info(f"Successfully consolidated transactions. Output saved to {output_path}")
        logger.info("\nFirst few records:")
        logger.info(result.to_string())
        
        # Print validation report
        logger.info("\n" + processor.generate_validation_report())
        
    except Exception as e:
        logger.error(f"Error processing files: {str(e)}")
        raise

if __name__ == "__main__":
    main()