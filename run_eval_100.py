#!/usr/bin/env python3
"""
Run 100-question evaluation against Greenside AI
"""

import requests
import json
import sys
from datetime import datetime
from eval_questions_100 import EVAL_QUESTIONS_100

API_URL = 'http://localhost:5000/ask'
TIMEOUT = 90  # seconds per question

def run_evaluation():
    results = []
    successful = 0
    failed = 0

    total = len(EVAL_QUESTIONS_100)
    print(f"\n{'='*60}")
    print(f"GREENSIDE AI - 100 QUESTION EVALUATION")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for i, q in enumerate(EVAL_QUESTIONS_100, 1):
        question = q['question']
        print(f"[{i:3d}/{total}] {question[:60]}...", end=' ', flush=True)

        try:
            response = requests.post(
                API_URL,
                json={'question': question},
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                failed += 1
                results.append({
                    'question': question,
                    'category': q['category'],
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                })
                continue

            data = response.json()
            answer = data.get('answer', '').lower()
            confidence = data.get('confidence', {}).get('score', 0)

            # Score
            keyword_hits = sum(1 for kw in q.get('expected_keywords', []) if kw.lower() in answer)
            keyword_total = len(q.get('expected_keywords', []))
            keyword_score = keyword_hits / keyword_total if keyword_total > 0 else 1.0

            product_hits = sum(1 for p in q.get('expected_products', []) if p.lower() in answer)
            product_total = len(q.get('expected_products', []))
            product_score = product_hits / max(product_total, 1)

            overall_score = (keyword_score * 0.6) + (product_score * 0.2) + (confidence / 100 * 0.2)

            print(f"✓ {confidence:.0f}% conf, {overall_score*100:.0f}% score")
            successful += 1

            results.append({
                'question': question,
                'category': q['category'],
                'success': True,
                'confidence': confidence,
                'keyword_score': round(keyword_score * 100, 1),
                'product_score': round(product_score * 100, 1),
                'overall_score': round(overall_score * 100, 1),
                'keywords_found': keyword_hits,
                'keywords_expected': keyword_total,
                'products_found': product_hits,
                'products_expected': product_total,
                'answer_length': len(answer)
            })

        except requests.exceptions.Timeout:
            print("❌ TIMEOUT")
            failed += 1
            results.append({
                'question': question,
                'category': q['category'],
                'success': False,
                'error': 'Timeout'
            })
        except Exception as e:
            print(f"❌ {str(e)[:30]}")
            failed += 1
            results.append({
                'question': question,
                'category': q['category'],
                'success': False,
                'error': str(e)
            })

    # Calculate summary
    successful_results = [r for r in results if r.get('success')]

    summary = {
        'total_questions': total,
        'successful': successful,
        'failed': failed,
        'success_rate': round(successful / total * 100, 1),
        'avg_confidence': round(sum(r['confidence'] for r in successful_results) / len(successful_results), 1) if successful_results else 0,
        'avg_keyword_score': round(sum(r['keyword_score'] for r in successful_results) / len(successful_results), 1) if successful_results else 0,
        'avg_product_score': round(sum(r['product_score'] for r in successful_results) / len(successful_results), 1) if successful_results else 0,
        'avg_overall_score': round(sum(r['overall_score'] for r in successful_results) / len(successful_results), 1) if successful_results else 0,
        'evaluated_at': datetime.now().isoformat()
    }

    # Category breakdown
    categories = {}
    for r in successful_results:
        cat = r.get('category', 'general')
        if cat not in categories:
            categories[cat] = {'count': 0, 'total_score': 0, 'total_conf': 0}
        categories[cat]['count'] += 1
        categories[cat]['total_score'] += r['overall_score']
        categories[cat]['total_conf'] += r['confidence']

    for cat in categories:
        categories[cat]['avg_score'] = round(categories[cat]['total_score'] / categories[cat]['count'], 1)
        categories[cat]['avg_confidence'] = round(categories[cat]['total_conf'] / categories[cat]['count'], 1)

    summary['by_category'] = categories

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Questions: {total} | Success: {successful} | Failed: {failed}")
    print(f"Average Confidence: {summary['avg_confidence']}%")
    print(f"Average Keyword Score: {summary['avg_keyword_score']}%")
    print(f"Average Product Score: {summary['avg_product_score']}%")
    print(f"Average Overall Score: {summary['avg_overall_score']}%")

    print(f"\nBy Category:")
    for cat, data in sorted(categories.items()):
        print(f"  {cat:15s}: {data['avg_score']:5.1f}% score, {data['avg_confidence']:5.1f}% conf ({data['count']} questions)")

    # Save results
    output = {
        'summary': summary,
        'results': results
    }

    output_file = f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Also save to database
    try:
        from fine_tuning import save_eval_results
        run_id = save_eval_results(output)
        print(f"Saved to database with run_id: {run_id}")
    except Exception as e:
        print(f"Warning: Could not save to database: {e}")

    return output


if __name__ == '__main__':
    run_evaluation()
