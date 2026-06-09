---
name: ucp-caching-design
description: Сгенерировать кеш-обвязку Spring Cache + Redis по Caching Style Guide (коды R-CACHE-*) — RedisCacheManager с per-cache TTL, JSON-сериализация, CacheSettings, @Cacheable/@CacheEvict, @EventListener-invalidation, паттерн cache-aside/write-through.
when_to_use: Триггеры — «закешируй X», «нужен Redis-кеш для Y», «настрой CacheManager». При добавлении кеша или настройке cache-backend.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Caching — проектирование

Ты генерируешь кеш-обвязку (CacheManager + CacheSettings + `@Cacheable`/`@CacheEvict`-аннотации + invalidation handlers) по Caching Style Guide. Цель — кеш, который проходит `ucp-caching-review` без findings.

## Инструкции

1. **Прочитай** `.claude/docs/backend/caching/caching-rules.md` (правила `R-CACHE-*`). Опционально — `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16` для PII), `backend/validation/validation-rules.md` (`R-VLD-CFG-*` для config).

2. **Уточни параметры:**
   - **Что кешируем** — конкретный read-метод. Имя cache (slug-style: `user-profiles`, `currencies`, `feature-flags`).
   - **Тип данных** — определит TTL:
     - Static reference (currencies, countries) → hours.
     - User profile / settings → 15–30 min.
     - Feature flags / config → 30–60 sec.
     - Heavy aggregations / reports → 5–10 min.
     - Money (balance, credit) → 5–30 sec **+ строгий evict-стратегия**.
   - **Доменные события для invalidation** — есть ли `<X>UpdatedEvent`, на который кеш должен реагировать?
   - **Hot key?** — если read >100 RPS, нужно refresh-ahead или distributed lock против stampede.
   - **Backend** — Redis (дефолт для прода), `ConcurrentMapCacheManager` (только для тестов).
   - **Сериализация** — JSON (`GenericJackson2JsonRedisSerializer`), не JDK.
   - **PII в значении?** — TTL короткий, в логах не светим, encryption at rest (Redis настройка).

3. **Принципы выбора паттерна:**

   | Сценарий | Паттерн | Реализация |
   |---|---|---|
   | Read-heavy, редко меняется | cache-aside | `@Cacheable` + `@CacheEvict` на write-партнёре |
   | Write update сразу читается | write-through | `@CachePut` |
   | Hot key, нельзя cache miss | refresh-ahead | `@Scheduled` каждые `TTL × 0.7` секунд |
   | Money / balance | cache-aside, **короткий** TTL | TTL ≤ 30s + `@CacheEvict` на каждом write |

4. **Произведи код.** Lombok-defaults обязательны (`JS-6.1`–`JS-6.7`). Не цитируй коды правил в комментариях кода (`JS-7.3`).

   ### 4.1. `CacheSettings` (`@ConfigurationProperties`)

   ```java
   // bootstrap/src/main/java/<pkg>/config/CacheSettings.java
   @ConfigurationProperties("cache")
   @Validated
   public record CacheSettings(
       @Valid @NotEmpty Map<String, CacheConfig> caches
   ) {
       public record CacheConfig(
           @NotNull Duration ttl,
           boolean disableNullValues
       ) {}
   }
   ```

   ### 4.2. `CacheConfig` (`@Configuration`)

   ```java
   // bootstrap/src/main/java/<pkg>/config/CacheConfiguration.java
   @Configuration
   @EnableCaching
   @EnableConfigurationProperties(CacheSettings.class)
   @RequiredArgsConstructor
   public class CacheConfiguration {

       @Bean
       RedisCacheManager cacheManager(
               RedisConnectionFactory cf,
               ObjectMapper mapper,
               CacheSettings settings) {

           var defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
               .serializeValuesWith(SerializationPair.fromSerializer(
                   new GenericJackson2JsonRedisSerializer(mapper)))
               .entryTtl(Duration.ofMinutes(15))           // дефолт; per-cache переопределяется
               .disableCachingNullValues();

           var perCache = settings.caches().entrySet().stream()
               .collect(Collectors.toMap(
                   Map.Entry::getKey,
                   e -> {
                       var cfg = defaultConfig.entryTtl(e.getValue().ttl());
                       return e.getValue().disableNullValues() ? cfg.disableCachingNullValues() : cfg;
                   }
               ));

           return RedisCacheManager.builder(cf)
               .cacheDefaults(defaultConfig)
               .withInitialCacheConfigurations(perCache)
               .build();
       }
   }
   ```

   ### 4.3. `application.yml` patch

   ```yaml
   spring:
     data:
       redis:
         host: ${REDIS_HOST:localhost}
         port: ${REDIS_PORT:6379}
     cache:
       type: redis

   cache:
     caches:
       user-profiles:
         ttl: 15m
         disable-null-values: true
       currencies:
         ttl: 6h
         disable-null-values: true
       feature-flags:
         ttl: 60s
         disable-null-values: true
       # money-related — короткий TTL + строгий evict
       user-balance:
         ttl: 30s
         disable-null-values: true

   management:
     metrics:
       enable:
         cache: true
   ```

   ### 4.4. Использование на read-методе (cache-aside дефолт)

   ```java
   @Component
   @RequiredArgsConstructor
   public class UserProfileService {

       private final UserProfileRepository repository;

       @Cacheable(cacheNames = "user-profiles", key = "#userId")
       public UserProfile findProfile(Long userId) {
           return repository.findById(userId, SelectMode.NO_LOCK)
               .orElseThrow(() -> new UserNotFoundException(userId));
       }
   }
   ```

   ### 4.5. Invalidation на write-методе

   ```java
   @Component
   @RequiredArgsConstructor
   @Transactional
   public class UpdateUserProfileCommandHandler implements UseCaseHandler<UpdateUserProfileCommand, UserProfile> {

       private final UserProfileRepository repository;

       @Override
       @CacheEvict(cacheNames = "user-profiles", key = "#cmd.userId()")
       public UserProfile handle(UpdateUserProfileCommand cmd) {
           var profile = repository.findById(cmd.userId(), SelectMode.FOR_UPDATE).orElseThrow();
           profile.update(cmd);
           repository.save(profile);
           return profile;
       }
   }
   ```

   ### 4.6. Invalidation через domain event

   Если update приходит из разных мест, развязывай через event:

   ```java
   @Component
   public class UserProfileCacheInvalidator {

       @EventListener
       @CacheEvict(cacheNames = "user-profiles", key = "#event.userId()")
       public void onUserProfileUpdated(UserProfileUpdatedEvent event) {
           // пустой метод — annotation делает работу
       }
   }
   ```

   ### 4.7. Refresh-ahead для hot keys

   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class TopProductsRefresher {

       private final ProductReadRepository repository;
       private final CacheManager cacheManager;

       // refresh каждые 5 минут, TTL 10 минут — гарантирует «нет cache miss»
       @Scheduled(fixedDelay = 5 * 60 * 1000)
       public void refresh() {
           try {
               var top = repository.findTop100();
               cacheManager.getCache("top-products").put("global", top);
               log.debug("Refreshed top-products cache, size={}", top.size());
           } catch (Exception e) {
               log.warn("Failed to refresh top-products cache", e);
           }
       }
   }
   ```

   ### 4.8. Money-cache (особый случай)

   Короткий TTL + `@CacheEvict` на каждом write. Если возможно — лучше **не кешировать**, а рассчитывать каждый раз.

   ```java
   @Component
   @RequiredArgsConstructor
   public class UserBalanceService {

       private final BalanceRepository repository;

       @Cacheable(cacheNames = "user-balance", key = "#userId")
       public Money getBalance(Long userId) {
           return repository.computeBalance(userId);
       }
   }

   // Каждый write-handler делает evict
   @Component
   @CacheEvict(cacheNames = "user-balance", key = "#cmd.userId()")
   public class ChargeUserBalanceCommandHandler implements UseCaseHandler<ChargeUserBalanceCommand, Money> { ... }
   ```

5. **Самопроверка перед выдачей** (`R-CACHE-*`):
   - `RedisCacheManager`, не `ConcurrentMapCacheManager` для прода.
   - `GenericJackson2JsonRedisSerializer`, не `JdkSerializationRedisSerializer`.
   - Per-cache TTL через `withInitialCacheConfigurations`.
   - Каждый кеш имеет explicit TTL в `application.yml`, не infinite.
   - `key = "..."` SpEL явно указан на `@Cacheable`-методах с 2+ параметрами.
   - `@CacheEvict` на write-методе того же агрегата.
   - Money-кеш — TTL ≤ 30s + строгий evict.
   - Hot keys — refresh-ahead через `@Scheduled`.
   - `@EnableCaching` + явный CacheManager-bean (не silent NoOp).
   - Нет PII в plain-ключе.

6. **Структура вывода:**
   1. **Решения** — что кешируется, какой паттерн (cache-aside/write-through/refresh-ahead), какой TTL и почему.
   2. **Дерево новых файлов** — `CacheSettings.java`, `CacheConfiguration.java`, изменения в Service/Handler.
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для existing-файлов** — `application.yml` (cache config + Redis), `bootstrap/build.gradle.kts` (`spring-boot-starter-data-redis`, `spring-boot-starter-cache`).
   5. **Заметки по реализации:**
      - Команды: `./gradlew compileJava`, `docker-compose up redis`, `./gradlew test --tests *CacheTest`.
      - **TODO для пользователя:** настроить Redis в `application-prod.yml` (cluster mode, password); добавить alert на `cache_gets_total{result=miss} / cache_gets_total > 0.3` (hit rate < 70%); проверить что значения сериализуемы Jackson (нет циклических ссылок).
   6. **Финальный шаг:** «после генерации запусти `ucp-caching-review` для верификации; добавь интеграционный тест с `Testcontainers` Redis».

## Что НЕ делает

- HTTP `Cache-Control` headers — это `ucp-api-design` (REST API).
- JWT JWK кеш — встроен в Spring Security (`AUTH-5`), отдельной обвязки не нужно.
- DB query cache — `ucp-pg-runtime-design` (если materialized views).
- Resilience cache-as-fallback — `ucp-integration-design` использует cache в fallback-методах, генерация cache-инфры — этот скилл.
- Кеш доменного агрегата целиком — нарушает `R-CACHE-WHERE-X2`, скилл откажется генерировать.

После — обязательно `ucp-caching-review` для верификации.

$ARGUMENTS
