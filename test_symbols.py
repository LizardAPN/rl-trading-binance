import asyncio
from pybit.unified_trading import HTTP

async def test_get_all_symbols():
    """Test function to fetch all available symbols from Bybit"""
    # Initialize HTTP session (without authentication for public endpoints)
    session = HTTP(testnet=False)
    
    try:
        # Fetch all linear (USDT perpetual) instruments
        response = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: session.get_instruments_info(category="linear")
        )
        
        if response.get("retCode") == 0:
            symbols = response.get("result", {}).get("list", [])
            print(f"Found {len(symbols)} instruments:")
            
            # Filter for USDT perpetual contracts
            usdt_contracts = [
                symbol for symbol in symbols 
                if symbol.get("quoteCoin") == "USDT" and symbol.get("status") == "Trading"
            ]
            
            print(f"Found {len(usdt_contracts)} USDT perpetual contracts:")
            for symbol in usdt_contracts[:10]:  # Show first 10
                print(f"  - {symbol.get('symbol')}: {symbol.get('baseCoin')}/{symbol.get('quoteCoin')}")
            
            if len(usdt_contracts) > 10:
                print(f"  ... and {len(usdt_contracts) - 10} more")
                
            # Return list of symbol names
            return [symbol.get("symbol") for symbol in usdt_contracts]
        else:
            print(f"Error: {response.get('retMsg')}")
            return []
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return []

if __name__ == "__main__":
    symbols = asyncio.run(test_get_all_symbols())
    print(f"\nReturned {len(symbols)} symbols")
