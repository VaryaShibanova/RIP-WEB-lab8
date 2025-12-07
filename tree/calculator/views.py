import random
import time
import requests
import threading
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

@csrf_exempt
def calculate_years(request):
    """
    Запуск асинхронного расчета calculated_year для ВСЕХ TreeItem заявки
    Вызывается когда модератор завершает заявку
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # ЛОГИРОВАНИЕ ДЛЯ ДЕБАГА
    print("=== INCOMING REQUEST TO DJANGO ===")
    print(f"📦 Generated callback token: {settings.CALLBACK_TOKEN}")
    print("Headers:", dict(request.headers))
    print("Raw body:", request.body)
    
    try:
        # ПРАВИЛЬНЫЙ ПАРСИНГ JSON
        data = json.loads(request.body)
        print("Parsed JSON data:", data)
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
        return JsonResponse({'error': 'Invalid JSON: ' + str(e)}, status=400)
    
    # Валидация
    required_fields = ['tree_id', 'tree_items']
    for field in required_fields:
        if field not in data:
            error_msg = f'Missing field: {field}'
            print("Validation error:", error_msg)
            return JsonResponse({'error': error_msg}, status=400)
    
    # Дополнительная валидация tree_items
    if not isinstance(data['tree_items'], list):
        return JsonResponse({'error': 'tree_items must be a list'}, status=400)
    
    for i, item in enumerate(data['tree_items']):
        item_fields = ['tree_item_id', 'anomaly_id', 'total_rings', 'anomalous_rings', 'anomaly_year']
        for field in item_fields:
            if field not in item:
                return JsonResponse({'error': f'Missing field {field} in tree_items[{i}]'}, status=400)
    
    print(f"Starting async calculations for tree {data['tree_id']} with {len(data['tree_items'])} items")
    
    # Запускаем асинхронные расчеты для каждого TreeItem
    thread = threading.Thread(
        target=process_all_calculations_async,
        args=(data['tree_id'], data['tree_items'])
    )
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'message': 'Async calculations started for all tree items',
        'tree_id': data['tree_id'],
        'total_items': len(data['tree_items']),
        'status': 'processing',
        'estimated_timing': '5-10 seconds per item',
        'callback_token': settings.CALLBACK_TOKEN
    })

def process_all_calculations_async(tree_id, tree_items):
    """
    Асинхронная обработка ВСЕХ TreeItem заявки с отправкой ВСЕХ результатов
    """
    print(f"🔄 Processing {len(tree_items)} items for tree {tree_id}")
    results = []
    
    # Для каждого TreeItem запускаем расчет
    for i, item in enumerate(tree_items):
        print(f"📝 Processing item {i+1}/{len(tree_items)}: tree_item_id={item['tree_item_id']}")
        
        # ЗАДЕРЖКА 5-10 секунд для КАЖДОГО элемента
        delay_seconds = random.randint(5, 10)
        print(f"⏳ Waiting {delay_seconds} seconds for item {item['tree_item_id']}")
        time.sleep(delay_seconds)
        
        # РАСЧЕТ ГОДА
        try:
            calculated_year = calculate_year_for_anomaly(
                item['total_rings'],
                item['anomalous_rings'],
                item['anomaly_year']
            )
            status = 'completed'
            print(f"✅ Calculation SUCCESS for item {item['tree_item_id']}: {calculated_year}")
        except Exception as e:
            calculated_year = 0
            status = 'failed'
            print(f"❌ Calculation FAILED for item {item['tree_item_id']}: {e}")
        
        # НАКАПЛИВАЕМ результат (не отправляем сразу!)
        results.append({
            'tree_item_id': item['tree_item_id'],
            'calculated_year': calculated_year,
            'status': status
        })
    
    # 👇 ОТПРАВЛЯЕМ ВСЕ РЕЗУЛЬТАТЫ ОДНИМ ЗАПРОСОМ
    print(f"🎯 All calculations completed for tree {tree_id}. Sending ALL results...")
    send_all_results_to_go_service(tree_id, results)

def calculate_year_for_anomaly(total_rings, anomalous_rings, anomaly_year):
    """Формула расчета calculated_year с улучшенной обработкой ошибок"""
    print(f"🔍 Calculating: total_rings={total_rings}, anomalous_rings='{anomalous_rings}', anomaly_year={anomaly_year}")
    
    # Валидация входных данных
    if not total_rings or total_rings <= 0:
        raise ValueError(f"Invalid total_rings: {total_rings}")
    
    if not anomaly_year or anomaly_year <= 0:
        raise ValueError(f"Invalid anomaly_year: {anomaly_year}")
    
    if not anomalous_rings or not anomalous_rings.strip():
        raise ValueError("Empty anomalous_rings")
    
    try:
        # Парсинг аномальных колец
        rings = [int(r.strip()) for r in anomalous_rings.split(',') if r.strip()]
        if not rings:
            raise ValueError("No valid rings found after parsing")
        
        max_ring = max(rings)
        print(f"   Parsed rings: {rings}, max_ring: {max_ring}")
        
        # Проверка валидности
        if max_ring > total_rings:
            raise ValueError(f"Max ring {max_ring} exceeds total rings {total_rings}")
        
        if any(ring <= 0 for ring in rings):
            raise ValueError(f"Invalid ring values: {rings}")
        
        calculated_year = anomaly_year + (total_rings - max_ring)
        print(f"   ✅ CALCULATION: {anomaly_year} + ({total_rings} - {max_ring}) = {calculated_year}")
        
        return calculated_year
        
    except ValueError as e:
        print(f"   ❌ CALCULATION ERROR: {e}")
        raise
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR: {e}")
        raise

def send_all_results_to_go_service(tree_id, results):
    """Отправка ВСЕХ результатов одним запросом"""
    callback_url = f"{settings.GO_SERVICE_URL}/api/asynctree/ageresult"
    
    payload = {
        'tree_id': tree_id,
        'message': 'All calculations completed',
        'results': results,  # 👈 ВЕСЬ массив результатов
        'total_items': len(results),
        'final_status': 'completed'
    }
    
    headers = {
        'Authorization': f'Bearer {settings.CALLBACK_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    print(f"📦 Sending ALL results to Go: {len(results)} items")
    print(f"   Token used: {settings.CALLBACK_TOKEN}")
    print(f"   Results: {results}")
    
    try:
        response = requests.put(callback_url, json=payload, headers=headers, timeout=30)
        print(f"✅ All results sent successfully: {response.status_code}")
        
        # Логируем ответ от Go
        if response.status_code == 200:
            response_data = response.json()
            print(f"📨 Go response: {response_data}")
        else:
            print(f"⚠️  Go returned status: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout while sending results to Go")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error while sending results to Go")
    except Exception as e:
        print(f"❌ Failed to send all results: {e}")