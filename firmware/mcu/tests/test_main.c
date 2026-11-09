/*
 * test_main.c — đăng ký và chạy mọi TEST_CASE trong các file test_*.c.
 */
#include "test.h"

typedef struct {
    const char *name;
    fly_test_fn fn;
} fly_test_case_t;

static fly_test_case_t cases[TEST_MAX_CASES];
static int case_count;

const char *fly_test_current = "";
int fly_test_checks = 0;
int fly_test_failures = 0;

void fly_test_register(const char *name, fly_test_fn fn)
{
    if (!name || !fn || case_count >= TEST_MAX_CASES) {
        return;
    }
    cases[case_count].name = name;
    cases[case_count].fn = fn;
    case_count++;
}

int main(void)
{
    int i;
    int passed = 0;
    int failed = 0;

    for (i = 0; i < case_count; i++) {
        fly_test_current = cases[i].name;
        fly_test_checks = 0;
        fly_test_failures = 0;
        cases[i].fn();
        if (fly_test_failures == 0) {
            passed++;
            printf("PASS %s\n", cases[i].name);
        } else {
            failed++;
            printf("FAIL %s (%d/%d checks failed)\n", cases[i].name, fly_test_failures,
                   fly_test_checks);
        }
    }

    if (failed != 0) {
        printf("FAIL %d\n", failed);
        printf("PASS %d\n", passed);
        return 1;
    }
    printf("PASS %d\n", passed);
    return 0;
}
