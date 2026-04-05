#!/bin/bash
# Скрипт для запуска тестов UTOS
# Usage: ./scripts/run_tests.sh [--smoke] [--regression] [--coverage]

set -e

cd /home/trader/trading_bots_v2

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "UTOS Test Suite"
echo "========================================="

# Флаги
RUN_SMOKE=false
RUN_REGRESSION=false
RUN_COVERAGE=false
RUN_ALL=true

# Парсинг аргументов
for arg in "$@"; do
    case $arg in
        --smoke)
            RUN_SMOKE=true
            RUN_ALL=false
            shift
            ;;
        --regression)
            RUN_REGRESSION=true
            RUN_ALL=false
            shift
            ;;
        --coverage)
            RUN_COVERAGE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--smoke] [--regression] [--coverage]"
            echo "  --smoke      Run only smoke tests (L1)"
            echo "  --regression Run only regression tests (L2)"
            echo "  --coverage   Run with coverage report"
            echo "  --help       Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# Если не указаны флаги, запускаем все
if [ "$RUN_ALL" = true ]; then
    RUN_SMOKE=true
    RUN_REGRESSION=true
fi

# Устанавливаем переменную окружения для тестовой БД
export UTOS_TEST_DB=false

# Функция для запуска pytest
run_pytest() {
    local test_path=$1
    local test_name=$2
    
    echo -e "\n${YELLOW}▶ Running $test_name...${NC}"
    
    if [ "$RUN_COVERAGE" = true ]; then
        pytest "$test_path" -v --tb=short --cov=trading_lib --cov-report=term --cov-report=html
    else
        pytest "$test_path" -v --tb=short
    fi
    
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ $test_name passed${NC}"
    else
        echo -e "${RED}✗ $test_name failed${NC}"
        exit $exit_code
    fi
}

# Запуск smoke-тестов (L1)
if [ "$RUN_SMOKE" = true ]; then
    run_pytest "tests/smoke/" "Smoke tests (L1)"
fi

# Запуск регрессионных тестов (L2)
if [ "$RUN_REGRESSION" = true ]; then
    run_pytest "tests/regression/" "Regression tests (L2)"
fi

echo -e "\n${GREEN}========================================="
echo "✓ All tests passed successfully!"
echo "=========================================${NC}"

if [ "$RUN_COVERAGE" = true ]; then
    echo -e "\nCoverage report generated in htmlcov/index.html"
fi