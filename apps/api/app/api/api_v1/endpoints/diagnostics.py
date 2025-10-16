"""
Diagnostic endpoints for debugging Railway deployment issues
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import os
import subprocess
import sys
import logging

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/chrome-status")
async def check_chrome_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check Chrome/Chromium and ChromeDriver installation status.

    Returns diagnostic information about Selenium dependencies.
    """
    result = {
        "environment_vars": {},
        "binary_paths": {},
        "versions": {},
        "python_packages": {},
        "errors": []
    }

    # Check environment variables
    env_vars = ["CHROME_BIN", "CHROMEDRIVER_PATH", "PATH"]
    for var in env_vars:
        result["environment_vars"][var] = os.environ.get(var, "NOT SET")

    # Check for Chrome/Chromium binary
    chromium_checks = ["chromium", "chromium-browser", "google-chrome", "chrome"]
    for binary in chromium_checks:
        try:
            proc = subprocess.run(
                ["which", binary],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                result["binary_paths"][binary] = proc.stdout.strip()
                # Try to get version
                try:
                    version_proc = subprocess.run(
                        [proc.stdout.strip(), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if version_proc.returncode == 0:
                        result["versions"][binary] = version_proc.stdout.strip()
                except Exception as e:
                    result["errors"].append(f"Failed to get {binary} version: {str(e)}")
            else:
                result["binary_paths"][binary] = "NOT FOUND"
        except Exception as e:
            result["errors"].append(f"Error checking {binary}: {str(e)}")

    # Check for ChromeDriver
    try:
        proc = subprocess.run(
            ["which", "chromedriver"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if proc.returncode == 0:
            result["binary_paths"]["chromedriver"] = proc.stdout.strip()
            # Try to get version
            try:
                version_proc = subprocess.run(
                    [proc.stdout.strip(), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_proc.returncode == 0:
                    result["versions"]["chromedriver"] = version_proc.stdout.strip()
            except Exception as e:
                result["errors"].append(f"Failed to get chromedriver version: {str(e)}")
        else:
            result["binary_paths"]["chromedriver"] = "NOT FOUND"
    except Exception as e:
        result["errors"].append(f"Error checking chromedriver: {str(e)}")

    # Check Python packages
    packages = ["selenium", "webdriver_manager"]
    for package in packages:
        try:
            __import__(package)
            result["python_packages"][package] = "INSTALLED"
        except ImportError:
            result["python_packages"][package] = "NOT INSTALLED"

    # Try to import and check Selenium
    try:
        from selenium import webdriver
        result["python_packages"]["selenium_import"] = "SUCCESS"
    except Exception as e:
        result["python_packages"]["selenium_import"] = f"FAILED: {str(e)}"

    return result


@router.get("/test-chrome-init")
async def test_chrome_initialization(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Attempt to initialize Chrome/Chromium with Selenium.

    Returns detailed error information if initialization fails.
    """
    result = {
        "status": "unknown",
        "message": "",
        "details": {}
    }

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        import subprocess

        # Detect Chrome binary
        chrome_bin = None
        for binary in ["chromium", "chromium-browser", "google-chrome"]:
            try:
                proc = subprocess.run(
                    ["which", binary],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if proc.returncode == 0:
                    chrome_bin = proc.stdout.strip()
                    result["details"]["chrome_binary_found"] = chrome_bin
                    break
            except:
                pass

        if not chrome_bin:
            result["status"] = "error"
            result["message"] = "Chrome/Chromium binary not found"
            return result

        # Detect ChromeDriver
        chromedriver_path = None
        try:
            proc = subprocess.run(
                ["which", "chromedriver"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                chromedriver_path = proc.stdout.strip()
                result["details"]["chromedriver_found"] = chromedriver_path
        except:
            pass

        if not chromedriver_path:
            result["status"] = "error"
            result["message"] = "ChromeDriver binary not found"
            return result

        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.binary_location = chrome_bin

        # Initialize Chrome
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Test navigation
        driver.get("https://www.google.com")
        result["details"]["page_title"] = driver.title

        # Cleanup
        driver.quit()

        result["status"] = "success"
        result["message"] = "Chrome initialized and navigated successfully"

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Chrome initialization failed: {type(e).__name__}: {str(e)}"
        import traceback
        result["details"]["traceback"] = traceback.format_exc()

    return result
