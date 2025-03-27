#!/bin/bash

# Создаем директорию для логов
mkdir -p test_results

# Собираем и запускаем тесты
docker compose build tests
docker compose run --rm --name eventcrafter_tests -v $(pwd)/test_results:/app/test_results tests

# Сохраняем код возврата
TEST_EXIT_CODE=$?

# Удаляем контейнер (хотя --rm должен это делать)
docker rm -f eventcrafter_tests 2>/dev/null || true

# Проверяем наличие файла с результатами
if [ -f "test_results/test_results.log" ]; then
    cat test_results/test_results.log
else
    echo "Test results file not found!"
fi

exit $TEST_EXIT_CODE