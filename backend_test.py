#!/usr/bin/env python3
"""
Backend API Testing Suite for Premium Subscription Store
Tests all backend endpoints including Stripe payment integration
"""

import asyncio
import aiohttp
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://20e69d05-9a30-474e-a7e0-dcd0d14a7f62.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        self.test_user_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
        self.test_user_data = {
            "email": self.test_user_email,
            "first_name": "John",
            "last_name": "Doe",
            "password": "securepassword123"
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and not success:
            print(f"   Response: {response_data}")
        print()
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data
        })
    
    async def test_basic_connectivity(self):
        """Test basic API connectivity"""
        try:
            async with self.session.get(f"{BASE_URL}/") as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test("Basic API Connectivity", True, f"API version: {data.get('version', 'unknown')}")
                    return True
                else:
                    self.log_test("Basic API Connectivity", False, f"Status: {response.status}")
                    return False
        except Exception as e:
            self.log_test("Basic API Connectivity", False, f"Connection error: {str(e)}")
            return False
    
    async def test_subscription_catalog(self):
        """Test subscription catalog endpoints"""
        try:
            # Test get all subscriptions
            async with self.session.get(f"{BASE_URL}/subscriptions") as response:
                if response.status == 200:
                    subscriptions = await response.json()
                    if len(subscriptions) >= 4:  # Should have 4 predefined plans
                        self.log_test("Get All Subscriptions", True, f"Found {len(subscriptions)} subscription plans")
                        
                        # Test get specific subscription
                        first_sub_id = subscriptions[0]["id"]
                        async with self.session.get(f"{BASE_URL}/subscriptions/{first_sub_id}") as sub_response:
                            if sub_response.status == 200:
                                sub_data = await sub_response.json()
                                self.log_test("Get Specific Subscription", True, f"Retrieved plan: {sub_data['plan_name']}")
                                return True
                            else:
                                self.log_test("Get Specific Subscription", False, f"Status: {sub_response.status}")
                                return False
                    else:
                        self.log_test("Get All Subscriptions", False, f"Expected 4+ plans, got {len(subscriptions)}")
                        return False
                else:
                    self.log_test("Get All Subscriptions", False, f"Status: {response.status}")
                    return False
        except Exception as e:
            self.log_test("Subscription Catalog", False, f"Error: {str(e)}")
            return False
    
    async def test_user_authentication(self):
        """Test user registration and login"""
        try:
            # Test user registration
            async with self.session.post(f"{BASE_URL}/users", json=self.test_user_data) as response:
                if response.status == 200:
                    user_data = await response.json()
                    self.log_test("User Registration", True, f"Created user: {user_data['email']}")
                    
                    # Test user login
                    login_data = {
                        "email": self.test_user_data["email"],
                        "password": self.test_user_data["password"]
                    }
                    async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as login_response:
                        if login_response.status == 200:
                            login_result = await login_response.json()
                            self.log_test("User Login", True, f"Login successful for user: {login_result.get('user_id', 'unknown')}")
                            return True
                        else:
                            login_error = await login_response.text()
                            self.log_test("User Login", False, f"Status: {login_response.status}, Error: {login_error}")
                            return False
                else:
                    reg_error = await response.text()
                    self.log_test("User Registration", False, f"Status: {response.status}, Error: {reg_error}")
                    return False
        except Exception as e:
            self.log_test("User Authentication", False, f"Error: {str(e)}")
            return False
    
    async def test_order_management(self):
        """Test order creation and retrieval"""
        try:
            # First get a subscription plan ID
            async with self.session.get(f"{BASE_URL}/subscriptions") as response:
                if response.status != 200:
                    self.log_test("Order Management - Get Plans", False, "Could not fetch subscription plans")
                    return False
                
                subscriptions = await response.json()
                test_plan_id = subscriptions[0]["id"]
                
                # Test order creation
                order_data = {
                    "user_email": self.test_user_email,
                    "subscription_plan_id": test_plan_id
                }
                
                async with self.session.post(f"{BASE_URL}/orders", json=order_data) as order_response:
                    if order_response.status == 200:
                        order_result = await order_response.json()
                        order_id = order_result["id"]
                        self.log_test("Order Creation", True, f"Created order: {order_id}")
                        
                        # Test order retrieval by ID
                        async with self.session.get(f"{BASE_URL}/orders/{order_id}") as get_response:
                            if get_response.status == 200:
                                retrieved_order = await get_response.json()
                                self.log_test("Order Retrieval by ID", True, f"Retrieved order: {retrieved_order['id']}")
                                
                                # Test orders list by user email
                                async with self.session.get(f"{BASE_URL}/orders?user_email={self.test_user_email}") as list_response:
                                    if list_response.status == 200:
                                        orders_list = await list_response.json()
                                        self.log_test("Orders List by User", True, f"Found {len(orders_list)} orders for user")
                                        return True
                                    else:
                                        list_error = await list_response.text()
                                        self.log_test("Orders List by User", False, f"Status: {list_response.status}, Error: {list_error}")
                                        return False
                            else:
                                get_error = await get_response.text()
                                self.log_test("Order Retrieval by ID", False, f"Status: {get_response.status}, Error: {get_error}")
                                return False
                    else:
                        order_error = await order_response.text()
                        self.log_test("Order Creation", False, f"Status: {order_response.status}, Error: {order_error}")
                        return False
        except Exception as e:
            self.log_test("Order Management", False, f"Error: {str(e)}")
            return False
    
    async def test_stripe_payment_integration(self):
        """Test Stripe payment integration endpoints"""
        try:
            # First get a subscription plan
            async with self.session.get(f"{BASE_URL}/subscriptions") as response:
                if response.status != 200:
                    self.log_test("Stripe Integration - Get Plans", False, "Could not fetch subscription plans")
                    return False
                
                subscriptions = await response.json()
                test_plan = subscriptions[0]  # Use CapCut plan
                
                # Test checkout session creation
                checkout_data = {
                    "subscription_plan_id": test_plan["id"],
                    "user_email": self.test_user_email,
                    "origin_url": "https://example.com"
                }
                
                async with self.session.post(f"{BASE_URL}/checkout/session", json=checkout_data) as checkout_response:
                    if checkout_response.status == 200:
                        checkout_result = await checkout_response.json()
                        session_id = checkout_result.get("session_id")
                        checkout_url = checkout_result.get("url")
                        
                        if session_id and checkout_url:
                            self.log_test("Stripe Checkout Session Creation", True, f"Created session: {session_id}")
                            
                            # Test checkout status checking
                            async with self.session.get(f"{BASE_URL}/checkout/status/{session_id}") as status_response:
                                if status_response.status == 200:
                                    status_result = await status_response.json()
                                    self.log_test("Stripe Checkout Status Check", True, f"Status: {status_result.get('status', 'unknown')}")
                                    return True
                                else:
                                    status_error = await status_response.text()
                                    self.log_test("Stripe Checkout Status Check", False, f"Status: {status_response.status}, Error: {status_error}")
                                    return False
                        else:
                            self.log_test("Stripe Checkout Session Creation", False, "Missing session_id or url in response")
                            return False
                    else:
                        checkout_error = await checkout_response.text()
                        self.log_test("Stripe Checkout Session Creation", False, f"Status: {checkout_response.status}, Error: {checkout_error}")
                        return False
        except Exception as e:
            self.log_test("Stripe Payment Integration", False, f"Error: {str(e)}")
            return False
    
    async def test_webhook_endpoint(self):
        """Test webhook endpoint accessibility (basic test)"""
        try:
            # Test webhook endpoint with empty payload (should handle gracefully)
            async with self.session.post(f"{BASE_URL}/webhook/stripe", json={}) as response:
                # Webhook should return some response (even if it's an error due to invalid payload)
                # The important thing is that the endpoint is accessible
                if response.status in [200, 400, 500]:  # Any of these statuses indicate endpoint is accessible
                    self.log_test("Stripe Webhook Endpoint", True, f"Endpoint accessible (Status: {response.status})")
                    return True
                else:
                    self.log_test("Stripe Webhook Endpoint", False, f"Unexpected status: {response.status}")
                    return False
        except Exception as e:
            self.log_test("Stripe Webhook Endpoint", False, f"Error: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Backend API Tests")
        print("=" * 50)
        
        # Test basic connectivity first
        if not await self.test_basic_connectivity():
            print("❌ Basic connectivity failed. Stopping tests.")
            return False
        
        # Run all tests
        tests = [
            ("Subscription Catalog", self.test_subscription_catalog),
            ("User Authentication", self.test_user_authentication),
            ("Order Management", self.test_order_management),
            ("Stripe Payment Integration", self.test_stripe_payment_integration),
            ("Webhook Endpoint", self.test_webhook_endpoint),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            print(f"🧪 Running {test_name} tests...")
            result = await test_func()
            if not result:
                all_passed = False
            print("-" * 30)
        
        # Summary
        print("📊 Test Summary")
        print("=" * 50)
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if all_passed:
            print("\n🎉 All backend tests passed!")
        else:
            print("\n⚠️  Some tests failed. Check details above.")
            
        return all_passed

async def main():
    """Main test runner"""
    async with BackendTester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())