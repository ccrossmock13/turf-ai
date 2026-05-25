import requests
import json
from datetime import datetime
import time

# Test configuration
BASE_URL = "http://localhost:5001"
RESULTS = []

print("="*80)
print("TURFIQ COMPREHENSIVE TEST SUITE")
print("="*80)
print(f"\nTesting against: {BASE_URL}")
print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Test categories
test_suite = {
    "State-Specific (BMPs)": [
        {
            "question": "What pre-emergent should I use for crabgrass in Florida?",
            "expected": ["Florida", "state", "timing"],
            "check_source": "Florida Bmp"
        },
        {
            "question": "Best fungicide program for Massachusetts bentgrass greens?",
            "expected": ["Massachusetts", "bentgrass", "fungicide"],
            "check_source": "Massachusetts Bmp"
        },
        {
            "question": "When should I overseed bermudagrass in North Carolina?",
            "expected": ["North Carolina", "bermudagrass", "overseed"],
            "check_source": "North Carolina Bmp"
        },
        {
            "question": "Irrigation schedule for Arizona summer bermudagrass?",
            "expected": ["Arizona", "irrigation", "summer"],
            "check_source": "Arizona Bmp"
        },
    ],
    
    "Safety Rules": [
        {
            "question": "How do I control weeds in my lawn with glyphosate?",
            "expected": ["non-selective", "kills all", "renovation"],
            "should_not_contain": ["apply to active turf", "safe for"]
        },
        {
            "question": "What PGR should I use on bentgrass greens?",
            "expected": ["Primo", "Trimmit", "Cutless"],
            "should_not_contain": ["PoaCure"]  # PoaCure is herbicide, not PGR
        },
    ],
    
    "Product Specificity": [
        {
            "question": "What rate should I apply Heritage fungicide?",
            "expected": ["0.16", "fl oz", "1000", "sq ft"],
            "should_not_contain": ["recommended rate", "labeled rate"]
        },
        {
            "question": "Compare Heritage vs Lexicon vs Xzemplar for dollar spot",
            "expected": ["Heritage", "Lexicon", "Xzemplar", "cost", "efficacy"],
            "should_not_contain": []
        },
        {
            "question": "What's the Primo MAXX rate for bermudagrass fairways?",
            "expected": ["5.5", "oz", "acre", "0.125"],
            "should_not_contain": ["recommended rate"]
        },
    ],
    
    "Complex Multi-Part": [
        {
            "question": "Build a 4-month fungicide rotation for bentgrass greens in Massachusetts that prevents resistance",
            "expected": ["rotation", "alternate", "FRAC", "resistance"],
            "should_not_contain": []
        },
        {
            "question": "What's the best integrated approach for Poa annua control including cultural practices?",
            "expected": ["herbicide", "cultural", "mowing", "fertility"],
            "should_not_contain": []
        },
    ],
    
    "Regional Detection": [
        {
            "question": "What bermudagrass varieties work best in Georgia?",
            "expected": ["Tifway", "Georgia", "variety"],
            "should_not_contain": []
        },
        {
            "question": "Snow mold prevention in Michigan?",
            "expected": ["snow mold", "Michigan", "fungicide"],
            "should_not_contain": []
        },
    ]
}

def test_question(question, expected, should_not_contain=None, check_source=None):
    """Test a single question"""
    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"question": question},
            timeout=30
        )
        
        if response.status_code != 200:
            return {
                "status": "FAIL",
                "error": f"HTTP {response.status_code}",
                "answer": None,
                "sources": []
            }
        
        data = response.json()
        answer = data.get('answer', '').lower()
        sources = data.get('sources', [])
        
        # Check expected keywords
        found_expected = [kw for kw in expected if kw.lower() in answer]
        missing_expected = [kw for kw in expected if kw.lower() not in answer]
        
        # Check should_not_contain
        found_forbidden = []
        if should_not_contain:
            found_forbidden = [kw for kw in should_not_contain if kw.lower() in answer]
        
        # Check if specific source is present
        source_found = False
        if check_source:
            source_found = any(check_source in s.get('name', '') for s in sources)
        
        # Determine pass/fail
        status = "PASS"
        if len(missing_expected) > len(expected) / 2:  # More than half missing
            status = "PARTIAL"
        if found_forbidden:
            status = "FAIL"
        if check_source and not source_found:
            status = "PARTIAL"
        
        return {
            "status": status,
            "answer": data.get('answer', ''),
            "sources": sources,
            "found_expected": found_expected,
            "missing_expected": missing_expected,
            "found_forbidden": found_forbidden,
            "source_found": source_found if check_source else None,
            "source_check": check_source
        }
        
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "answer": None,
            "sources": []
        }

# Run all tests
total_tests = 0
passed = 0
partial = 0
failed = 0

for category, tests in test_suite.items():
    print(f"\n{'='*80}")
    print(f"{category.upper()}")
    print(f"{'='*80}\n")
    
    for test in tests:
        total_tests += 1
        question = test['question']
        
        print(f"Q: {question}")
        
        result = test_question(
            question,
            test['expected'],
            test.get('should_not_contain'),
            test.get('check_source')
        )
        
        # Store result
        RESULTS.append({
            "category": category,
            "question": question,
            **result
        })
        
        # Display result
        status_symbol = {
            "PASS": "✅",
            "PARTIAL": "⚠️",
            "FAIL": "❌",
            "ERROR": "💥"
        }
        
        print(f"{status_symbol.get(result['status'], '?')} {result['status']}")
        
        if result['status'] == "PASS":
            passed += 1
        elif result['status'] == "PARTIAL":
            partial += 1
        else:
            failed += 1
        
        # Show details
        if result.get('found_expected'):
            print(f"   ✓ Found: {', '.join(result['found_expected'][:3])}")
        
        if result.get('missing_expected'):
            print(f"   ✗ Missing: {', '.join(result['missing_expected'][:3])}")
        
        if result.get('found_forbidden'):
            print(f"   ⚠ FORBIDDEN FOUND: {', '.join(result['found_forbidden'])}")
        
        if result.get('source_check'):
            if result.get('source_found'):
                print(f"   ✓ Source found: {result['source_check']}")
            else:
                print(f"   ✗ Source missing: {result['source_check']}")
        
        if result.get('sources'):
            print(f"   📚 Sources: {len(result['sources'])} provided")
            # Show first 3 sources
            for i, src in enumerate(result['sources'][:3], 1):
                url_status = "✓" if src.get('url') else "✗"
                print(f"      {i}. {src.get('name', 'Unknown')} {url_status}")
        
        if result.get('error'):
            print(f"   ERROR: {result['error']}")
        
        print()
        time.sleep(0.5)  # Don't hammer the server

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}\n")

print(f"Total Tests: {total_tests}")
print(f"✅ Passed: {passed} ({passed/total_tests*100:.1f}%)")
print(f"⚠️  Partial: {partial} ({partial/total_tests*100:.1f}%)")
print(f"❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")

# Category breakdown
print(f"\n{'-'*80}")
print("BY CATEGORY:")
print(f"{'-'*80}\n")

for category in test_suite.keys():
    cat_results = [r for r in RESULTS if r['category'] == category]
    cat_passed = len([r for r in cat_results if r['status'] == 'PASS'])
    cat_total = len(cat_results)
    print(f"{category}: {cat_passed}/{cat_total} ({cat_passed/cat_total*100:.0f}%)")

# Source URL check
print(f"\n{'-'*80}")
print("SOURCE URL VALIDATION:")
print(f"{'-'*80}\n")

total_sources = 0
working_urls = 0

for result in RESULTS:
    for source in result.get('sources', []):
        total_sources += 1
        if source.get('url'):
            working_urls += 1

print(f"Total sources returned: {total_sources}")
print(f"With valid URLs: {working_urls} ({working_urls/total_sources*100:.1f}%)")
print(f"Broken/missing: {total_sources - working_urls}")

# State BMP detection
print(f"\n{'-'*80}")
print("STATE BMP DETECTION:")
print(f"{'-'*80}\n")

state_tests = [r for r in RESULTS if r['category'] == 'State-Specific (BMPs)']
state_bmp_found = len([r for r in state_tests if r.get('source_found')])

print(f"State-specific questions: {len(state_tests)}")
print(f"State BMP cited: {state_bmp_found}/{len(state_tests)} ({state_bmp_found/len(state_tests)*100:.0f}%)")

# Safety rule compliance
print(f"\n{'-'*80}")
print("SAFETY RULE COMPLIANCE:")
print(f"{'-'*80}\n")

safety_tests = [r for r in RESULTS if r['category'] == 'Safety Rules']
safety_violations = len([r for r in safety_tests if r.get('found_forbidden')])

print(f"Safety tests: {len(safety_tests)}")
print(f"Violations detected: {safety_violations}")
if safety_violations == 0:
    print("✅ All safety rules enforced correctly")
else:
    print(f"❌ {safety_violations} safety violations found!")

# Save detailed results
filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(filename, 'w') as f:
    json.dump({
        'test_date': datetime.now().isoformat(),
        'summary': {
            'total': total_tests,
            'passed': passed,
            'partial': partial,
            'failed': failed,
            'pass_rate': passed/total_tests*100
        },
        'results': RESULTS
    }, f, indent=2)

print(f"\n✅ Detailed results saved to: {filename}")

# Final grade
pass_rate = (passed + partial * 0.5) / total_tests * 100
print(f"\n{'='*80}")
print(f"FINAL GRADE: {pass_rate:.1f}%")
if pass_rate >= 90:
    print("🎉 EXCELLENT - Production Ready")
elif pass_rate >= 75:
    print("👍 GOOD - Minor improvements needed")
elif pass_rate >= 60:
    print("⚠️  FAIR - Significant improvements needed")
else:
    print("❌ NEEDS WORK - Major issues to address")
print(f"{'='*80}\n")