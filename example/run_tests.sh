#!/bin/bash

# Создаем директории
mkdir -p test_results

# Очищаем предыдущие результаты
rm -f test_results/test_results.log

# Собираем и запускаем тесты
docker compose build tests && \
docker compose run --rm --name eventcrafter_tests \
  -v $(pwd)/test_results:/app/test_results \
  tests pytest -v --cov=src --cov-report=xml:test_results/coverage.xml tests/

# Проверяем наличие файла результатов
if [ ! -f "test_results/coverage.xml" ]; then
  echo "ERROR: Test coverage file not generated!"
  exit 1
fi

# Проверяем наличие файла с результатами
if [ -f "test_results/test_results.log" ]; then
    cat test_results/test_results.log
else
    echo "Test results file not found!"
fi