#!/usr/bin/env python3
"""
Fantrax Cookie Generator

This script helps users generate a Fantrax login cookie file
that can be uploaded to connect their Fantrax account to A Fine Wine Dynasty.

Usage:
    python generate_fantrax_cookie.py

The script will:
1. Open a Chrome browser window
2. Navigate to Fantrax login page
3. Wait 30 seconds for you to log in
4. Save your login cookies to 'fantrax_login.cookie'
5. You can then upload this file in the app

Requirements:
    - Chrome browser installed
    - selenium package (pip install selenium)
    - webdriver-manager package (pip install webdriver-manager)
"""

import pickle
import time
import sys
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("ERROR: Required packages not installed")
    print("\nPlease install required packages:")
    print("  pip install selenium webdriver-manager")
    sys.exit(1)


def generate_fantrax_cookie():
    """Generate Fantrax login cookie file"""

    print("=" * 60)
    print("Fantrax Cookie Generator")
    print("=" * 60)
    print("\nThis script will help you connect your Fantrax account")
    print("to A Fine Wine Dynasty.\n")

    print("Steps:")
    print("1. A Chrome browser window will open")
    print("2. Log in to your Fantrax account")
    print("3. After 30 seconds, your login will be saved")
    print("4. Upload the generated file in the app\n")

    input("Press Enter to continue...")

    output_file = "fantrax_login.cookie"

    try:
        print("\nInitializing Chrome browser...")

        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Keep browser visible so user can log in
        # chrome_options.add_argument("--headless")  # Commented out

        # Initialize Chrome driver
        print("Downloading Chrome driver if needed...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            # Navigate to Fantrax login page
            fantrax_login_url = "https://www.fantrax.com/login"
            print(f"\nOpening Fantrax login page: {fantrax_login_url}")
            driver.get(fantrax_login_url)

            print("\n" + "=" * 60)
            print("PLEASE LOG IN TO FANTRAX IN THE BROWSER WINDOW")
            print("=" * 60)
            print("\nYou have 30 seconds to complete the login.")
            print("After logging in, just wait - the script will continue automatically.")
            print("\nCountdown:")

            # Countdown timer
            for i in range(30, 0, -1):
                print(f"  {i} seconds remaining...", end='\r')
                time.sleep(1)

            print("\n\nRetrieving cookies...")

            # Get cookies
            cookies = driver.get_cookies()

            if not cookies:
                print("\nWARNING: No cookies found. Did you log in?")
                retry = input("Try again? (y/n): ")
                if retry.lower() == 'y':
                    print("\nWaiting another 30 seconds...")
                    for i in range(30, 0, -1):
                        print(f"  {i} seconds remaining...", end='\r')
                        time.sleep(1)
                    cookies = driver.get_cookies()

            if not cookies:
                print("\nERROR: Still no cookies found. Please try running the script again.")
                return False

            # Save cookies to file
            print(f"\nSaving cookies to {output_file}...")
            with open(output_file, "wb") as f:
                pickle.dump(cookies, f)

            print("\n" + "=" * 60)
            print("SUCCESS! Cookie file generated")
            print("=" * 60)
            print(f"\nCookie file saved as: {output_file}")
            print(f"File location: {Path(output_file).absolute()}")
            print(f"Number of cookies: {len(cookies)}")

            print("\nNext steps:")
            print("1. Go to A Fine Wine Dynasty app")
            print("2. Navigate to Integrations > Fantrax")
            print("3. Upload this cookie file")
            print("4. Connect your Fantrax leagues!")

            return True

        finally:
            print("\nClosing browser...")
            driver.quit()

    except Exception as e:
        print(f"\nERROR: Failed to generate cookie file")
        print(f"Error details: {str(e)}")
        print("\nTroubleshooting:")
        print("- Make sure Chrome browser is installed")
        print("- Check your internet connection")
        print("- Try running the script again")
        return False


def main():
    """Main function"""
    try:
        success = generate_fantrax_cookie()
        if success:
            print("\n✅ Cookie generation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Cookie generation failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
