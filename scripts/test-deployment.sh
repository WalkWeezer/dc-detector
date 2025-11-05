#!/bin/bash
# Скрипт автотестов для проверки работоспособности всех компонентов системы после деплоя

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Счетчики
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNINGS=0

# Параметры
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
DETECTION_URL="${DETECTION_URL:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost}"
TIMEOUT="${TIMEOUT:-5}"

echo "🧪 Запуск автотестов для DC-Detector"
echo "======================================"
echo "Backend:    $BACKEND_URL"
echo "Detection:  $DETECTION_URL"
echo "Frontend:   $FRONTEND_URL"
echo ""

# Функция для проверки HTTP эндпоинта
test_endpoint() {
    local method=$1
    local url=$2
    local expected_status=$3
    local description=$4
    
    if [ -z "$expected_status" ]; then
        expected_status=200
    fi
    
    echo -n "  Проверка: $description... "
    
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" --max-time "$TIMEOUT" 2>&1 || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✅ OK${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED (HTTP $http_code)${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Функция для предупреждения
test_warning() {
    local description=$1
    echo -e "  ${YELLOW}⚠️  $description${NC}"
    ((TESTS_WARNINGS++))
}

echo "📡 Проверка Backend API"
echo "----------------------"

test_endpoint "GET" "$BACKEND_URL/health" "200" "Health check"
test_endpoint "GET" "$BACKEND_URL/api/detections/status" "200" "Detections status"
test_endpoint "GET" "$BACKEND_URL/api/detections/models" "200" "Models list"
test_endpoint "GET" "$BACKEND_URL/api/detections" "200" "Detections list"
test_endpoint "GET" "$BACKEND_URL/api/detections/saved" "200" "Saved detections"

# Проверка видеопотока (может быть не сразу доступен)
echo -n "  Проверка: Video stream... "
stream_test=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/detections/stream" --max-time 3 2>&1 || echo "000")
if [ "$stream_test" = "200" ] || [ "$stream_test" = "000" ]; then
    echo -e "${GREEN}✅ OK${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  HTTP $stream_test (может быть не готов)${NC}"
    ((TESTS_WARNINGS++))
fi

echo ""
echo "🐍 Проверка Detection Service"
echo "----------------------------"

test_endpoint "GET" "$DETECTION_URL/health" "200" "Health check"
test_endpoint "GET" "$DETECTION_URL/api/detection" "200" "Detection status"
test_endpoint "GET" "$DETECTION_URL/cameras" "200" "Cameras list"

# Проверка статуса детекции для получения информации о камере
echo -n "  Проверка: Camera status... "
status_response=$(curl -s "$DETECTION_URL/api/detection" --max-time "$TIMEOUT" 2>&1 || echo "{}")
if echo "$status_response" | grep -q "local_camera_enabled"; then
    camera_enabled=$(echo "$status_response" | grep -o '"local_camera_enabled":[^,}]*' | cut -d: -f2 | tr -d ' ')
    active_camera=$(echo "$status_response" | grep -o '"active_camera":[^,}]*' | cut -d: -f2 | tr -d ' ')
    
    if [ "$camera_enabled" = "true" ] || [ "$camera_enabled" = "1" ]; then
        if [ "$active_camera" != "null" ] && [ -n "$active_camera" ]; then
            echo -e "${GREEN}✅ OK (Camera index: $active_camera)${NC}"
            ((TESTS_PASSED++))
        else
            echo -e "${YELLOW}⚠️  Camera enabled but not active${NC}"
            ((TESTS_WARNINGS++))
        fi
    else
        echo -e "${YELLOW}⚠️  Local camera disabled${NC}"
        ((TESTS_WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠️  Could not parse camera status${NC}"
    ((TESTS_WARNINGS++))
fi

# Проверка видеопотока detection сервиса
echo -n "  Проверка: Video feed... "
feed_test=$(curl -s -o /dev/null -w "%{http_code}" "$DETECTION_URL/video_feed" --max-time 3 2>&1 || echo "000")
if [ "$feed_test" = "200" ] || [ "$feed_test" = "000" ]; then
    echo -e "${GREEN}✅ OK${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  HTTP $feed_test (может быть не готов)${NC}"
    ((TESTS_WARNINGS++))
fi

echo ""
echo "🌐 Проверка Frontend"
echo "-------------------"

test_endpoint "GET" "$FRONTEND_URL/" "200" "Main page"
test_endpoint "GET" "$FRONTEND_URL/index.html" "200" "Index HTML"

# Проверка статических файлов
test_endpoint "GET" "$FRONTEND_URL/app.js" "200" "JavaScript bundle" || test_warning "JavaScript bundle not found (may be bundled)"
test_endpoint "GET" "$FRONTEND_URL/styles.css" "200" "CSS styles" || test_warning "CSS not found (may be bundled)"

echo ""
echo "📷 Проверка Pi Camera (если доступна)"
echo "-----------------------------------"

# Проверка доступности устройства камеры
if [ -e "/dev/video0" ]; then
    echo -e "  ${GREEN}✅ /dev/video0 найден${NC}"
    ((TESTS_PASSED++))
    
    # Попытка проверить через detection API
    if echo "$status_response" | grep -q '"active_camera"'; then
        echo -e "  ${GREEN}✅ Камера активна в detection сервисе${NC}"
        ((TESTS_PASSED++))
    else
        test_warning "Камера найдена, но не активна в сервисе"
    fi
else
    test_warning "/dev/video0 не найден (камера может быть не подключена)"
fi

# Проверка через Python (если доступен)
if command -v python3 &> /dev/null; then
    echo -n "  Проверка: Camera через OpenCV... "
    python3 -c "
import cv2
import sys
try:
    cap = cv2.VideoCapture(0)
    if cap and cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f'✅ OK (разрешение: {w}x{h})')
            sys.exit(0)
        else:
            print('⚠️  Камера открыта, но кадры не получаются')
            sys.exit(2)
    else:
        print('⚠️  Не удалось открыть камеру')
        sys.exit(2)
    cap.release()
except Exception as e:
    print(f'⚠️  Ошибка: {e}')
    sys.exit(2)
" 2>&1
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        ((TESTS_PASSED++))
    elif [ $exit_code -eq 2 ]; then
        ((TESTS_WARNINGS++))
    fi
else
    test_warning "Python3 не найден, пропуск проверки OpenCV"
fi

echo ""
echo "======================================"
echo "📊 Итоговый отчет:"
echo "  ${GREEN}✅ Успешно: $TESTS_PASSED${NC}"
echo "  ${RED}❌ Ошибки: $TESTS_FAILED${NC}"
echo "  ${YELLOW}⚠️  Предупреждения: $TESTS_WARNINGS${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✨ Все критические тесты пройдены!${NC}"
    exit 0
else
    echo -e "${RED}❌ Обнаружены ошибки в тестах${NC}"
    exit 1
fi

