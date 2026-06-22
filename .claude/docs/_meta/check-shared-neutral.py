#!/usr/bin/env python3
"""D (enforced граница): shared rules-index не должен содержать framework-специфичных
токенов — нейтральный интент, реализация уходит в <lang>/style-guide. Делает границу
«методология vs реализация» проверяемой машинно (как языковую ось), а не только прозой.

Запуск: python3 .claude/docs/_meta/check-shared-neutral.py [docs_dir]
Exit 1 при находках. Шапка-blockquote (> …) пропускается — там намеренно называется стек
каждого биндинга. Langspecific-concern'ы (они и ЕСТЬ биндинг) исключены.
"""
import re
import sys
from pathlib import Path

DOCS = Path(sys.argv[1] if len(sys.argv) > 1 else ".claude/docs")

# Langspecific concern'ы — это сам биндинг, framework-токены там легитимны (исключаем).
LANGSPECIFIC = {"jooq", "sqlalchemy", "java", "python-style", "python-bootstrap",
                "spring-bootstrap", "test-strategy", "python-test-strategy"}

# Курируемый denylist именно FRAMEWORK-специфики (не названия паттернов вроде circuit breaker).
DENY = re.compile(
    r"@(?:CircuitBreaker|Bulkhead|Retry|Retryable|Cacheable|CacheEvict|Caching|KafkaListener|"
    r"Scheduled|Async|PreAuthorize|Slf4j|Component|Service|Repository|Bean|Configuration|"
    r"SpringBootApplication|TransactionalEventListener|ConfigurationProperties|Validated|"
    r"EnableCaching|MockitoBean|WebMvcTest|RegisterExtension|DynamicPropertySource)\b"
    r"|\bResilience4j\b|\bOkHttp\w*\b|\bHikariCP\b|\bMicrometer\b|\bLogback\b|\bKafkaTemplate\b"
    r"|\bjOOQ\b|\bJOOQ\b|\bJdbcTemplate\b|\bArchUnit\b|\bSpotBugs\b|\bFindSecBugs\b|\bLiquibase\b"
    r"|\bHibernate\b|\bTomcat\b|\bNetty\b|\bRestClient\b|\bWebClient\b|\bRestTemplate\b"
    r"|\bWireMock\b|\bMapStruct\b|\bLombok\b|\bspring(?:-boot)?\.[a-z]|\borg\.springframework\b"
    r"|\bGradle\b|\bMockito\b|\bSpring Boot\b|\bSpring Security\b|\bSpring Cloud\b"
    # расширение B: Java-вокабуляр мимо первой версии denylist
    r"|@Transactional\b|@Retryable\b|@Around\b|@Enumerated\b|@SuppressFBWarnings\b"
    r"|\bSelectMode\b|\bJakarta\b|\bUseCaseCommand\b|\bUseCaseQuery\b|\bUseCaseEmptyResult\b"
    r"|\bSimpleGrantedAuthority\b|\bJwtAuthenticationConverter\b|\bBCryptPasswordEncoder\b"
    r"|\bSecureRandom\b|\bRestControllerAdvice\b|`record`"
)

problems = []
for rules in sorted(DOCS.glob("**/*-rules.md")):
    concern = rules.parent.name
    # frontend/e2e single-stack concern'ы — это сам биндинг (React+TS / Playwright),
    # framework-токены там легитимны; в neutral-check не входят (как LANGSPECIFIC).
    relp = rules.relative_to(DOCS).as_posix()
    if "/java/" in relp or "/python/" in relp or concern.startswith(("fe-","e2e-")) or concern=="_meta":
        continue
    in_header = True
    for i, line in enumerate(rules.read_text(encoding="utf-8").splitlines(), 1):
        if in_header:
            if line.startswith("## "):
                in_header = False
            else:
                continue  # шапка/blockquote — пропускаем
        # Двойная иллюстрация «(Java: X; Python: Y)» — легитимна (нейтральный интент
        # с примерами обоих биндингов, как в пилоте error-handling). Пропускаем строку,
        # если рядом с Java-токеном есть python-side маркер.
        PY_MARK = re.search(r"Python|Py\b|FastAPI|SQLAlchemy|Pydantic|aiokafka|httpx|"
                            r"uvicorn|asyncio|bandit|ruff|pip-audit|argon2|pytest|structlog", line)
        if PY_MARK and re.search(r"Java\b|Spring|JPA", line):
            continue
        for m in DENY.finditer(line):
            problems.append((rules.relative_to(DOCS).as_posix(), i, m.group(0), line.strip()[:90]))

if not problems:
    print("✓ shared rules-index нейтральны — framework-токенов в телах нет")
    sys.exit(0)

print(f"✗ найдено {len(problems)} framework-токенов в shared rules-index (должны быть в <lang>/style-guide):")
for f, ln, tok, snip in problems:
    print(f"  {f}:{ln}  [{tok}]  {snip}")
sys.exit(1)
