"""
Quick setup test script to verify all APIs and configurations are working
"""

import sys
import os

def test_imports():
    """Test if all required packages are installed"""
    print("Testing imports...")
    try:
        import requests
        import openai
        from scrapfly import ScrapflyClient
        from bs4 import BeautifulSoup
        from dotenv import load_dotenv
        print("✓ All packages imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Run: pip install -r requirements.txt")
        return False


def test_env_file():
    """Test if .env file exists and has required variables"""
    print("\nTesting .env file...")
    
    if not os.path.exists('.env'):
        print("✗ .env file not found")
        print("Run: cp .env.example .env")
        print("Then edit .env with your API keys")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'SERPER_API_KEY',
        'SCRAPFLY_API_KEY',
        'RAPIDAPI_KEY',
        'OPENAI_API_KEY',
        'SMTP_USERNAME',
        'SMTP_PASSWORD',
        'FROM_EMAIL'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"✗ Missing environment variables: {', '.join(missing)}")
        return False
    
    print("✓ .env file configured correctly")
    return True


def test_config():
    """Test if config loads correctly"""
    print("\nTesting config.py...")
    try:
        import config
        
        checks = {
            'SERPER_API_KEY': config.SERPER_API_KEY,
            'SCRAPFLY_API_KEY': config.SCRAPFLY_API_KEY,
            'RAPIDAPI_KEY': config.RAPIDAPI_KEY,
            'OPENAI_API_KEY': config.OPENAI_API_KEY,
            'SMTP_USERNAME': config.SMTP_USERNAME,
        }
        
        for key, value in checks.items():
            if not value or value == "":
                print(f"✗ {key} is empty")
                return False
        
        print("✓ Configuration loaded successfully")
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


def test_data_directory():
    """Test if data directory exists"""
    print("\nTesting data directory...")
    
    if not os.path.exists('data'):
        print("Creating data directory...")
        os.makedirs('data', exist_ok=True)
    
    print("✓ Data directory exists")
    return True


def test_api_connections():
    """Test basic API connections (without heavy requests)"""
    print("\nTesting API connections...")
    
    try:
        import config
        
        # Test OpenAI (just verify key format)
        if config.OPENAI_API_KEY.startswith('sk-'):
            print("✓ OpenAI API key format looks correct")
        else:
            print("⚠ OpenAI API key format might be incorrect")
        
        # Test Scrapfly client initialization
        from scrapfly import ScrapflyClient
        scrapfly = ScrapflyClient(key=config.SCRAPFLY_API_KEY)
        print("✓ Scrapfly client initialized")
        
        # Test Serper API key format
        if len(config.SERPER_API_KEY) > 20:
            print("✓ Serper API key format looks correct")
        else:
            print("⚠ Serper API key format might be incorrect")
        
        # Test RapidAPI key format
        if len(config.RAPIDAPI_KEY) > 20:
            print("✓ RapidAPI key format looks correct")
        else:
            print("⚠ RapidAPI key format might be incorrect")
        
        return True
        
    except Exception as e:
        print(f"✗ API connection error: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("COLD EMAIL TOOL - SETUP TEST")
    print("="*60)
    
    tests = [
        ("Package imports", test_imports),
        ("Environment file", test_env_file),
        ("Configuration", test_config),
        ("Data directory", test_data_directory),
        ("API connections", test_api_connections),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            results.append((name, test_func()))
        except Exception as e:
            print(f"✗ {name} failed with error: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "-"*60)
    print(f"Results: {passed}/{total} tests passed")
    print("-"*60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Run: python main.py")
        print("2. Choose option 1 to test scraper with a small batch")
        print("3. Review scraped data in data/scraped_companies.json")
        print("4. Choose option 2 to send test emails")
    else:
        print("\n⚠️ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Run: pip install -r requirements.txt")
        print("- Ensure .env file exists with all API keys")
        print("- Check that API keys are valid and active")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

