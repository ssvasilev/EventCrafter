#!/bin/bash

# Создаем директории
mkdir -p test_results

# Очищаем предыдущие результаты
rm -f test_results/test_results.log

# Собираем и запускаем тесты
docker compose build tests && \
docker compose run --rm --name eventcrafter_tests \
  -v $(pwd)/test_results:/app/test_results \
  tests

# Проверяем наличие файла результатов
if [ ! -f "test_results/test_results.log" ]; then
  echo "ERROR: Test results file not generated!"
  exit 1
fi

# Сохраняем код возврата
TEST_EXIT_CODE=$?

# Проверяем наличие файла с результатами
if [ -f "test_results/test_results.log" ]; then
    cat test_results/test_results.log
else
    echo "Test results file not found!"
fi

exit $TEST_EXIT_CODE
