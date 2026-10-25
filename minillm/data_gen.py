#!/usr/bin/env python3
"""Generate a synthetic Unity C# corpus for training the mini LLM."""
import random
import pathlib

random.seed(7)
OUT = pathlib.Path(__file__).parent / 'data' / 'scripts'
OUT.mkdir(parents=True, exist_ok=True)

NAMES = {
    'mover2d': ['PlayerMove', 'HeroMove', 'UnitMover', 'PlayerController2D'],
    'topdown': ['TopDownMove', 'PlayerMovement', 'CharacterMover', 'WASDMove'],
    'projectile': ['BulletMove', 'Projectile', 'ArrowFly', 'LaserShot'],
    'homing': ['HomingBullet', 'SeekingMissile', 'HomingMissile', 'TrackBullet'],
    'shooter': ['PlayerShooting', 'WeaponFire', 'GunController', 'Shooter'],
    'health': ['Health', 'Damageable', 'HitPoints', 'UnitHealth'],
    'manager': ['GameManager', 'StageManager', 'RunManager', 'ScoreManager'],
    'loader': ['LoadingSceneManager', 'SceneLoader', 'LoadScreen', 'LevelLoader'],
    'button': ['IntroButton', 'MenuButton', 'UIHoverButton', 'StartButton'],
    'asset': ['PlayerData', 'UnitData', 'ItemData', 'CharacterData'],
    'pickup': ['CoinPickup', 'ItemPickup', 'HealthOrb', 'Gem'],
    'camera': ['CameraFollow', 'SmoothCamera', 'CameraRig', 'FollowCam'],
    'audio': ['AudioManager', 'SoundManager', 'SfxPlayer', 'AudioHub'],
    'spawner': ['EnemySpawner', 'WaveSpawner', 'SpawnManager', 'MobSpawner'],
    'enemy': ['EnemyAI', 'Chaser', 'EnemyController', 'MeleeEnemy'],
    'pool': ['BulletPool', 'ObjectPool', 'PoolManager', 'ProjectilePool'],
}
F = ['speed', 'moveSpeed', 'flySpeed', 'travelSpeed']


def pick(key):
    return random.choice(NAMES[key])


def val(base, spread=0.5):
    return round(base * random.uniform(1 - spread, 1 + spread), 1)


def maybe(line, p=0.35):
    return line if random.random() < p else ''


def mover2d():
    cls = pick('mover2d'); sp = val(5)
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private float moveSpeed = {sp}f;
    [SerializeField] private float sprintMultiplier = {round(random.uniform(1.4,2.2),1)}f;
    private Rigidbody2D rb;
    private Vector2 moveInput;

    private void Awake()
    {{
        rb = GetComponent<Rigidbody2D>();
    }}

    private void Update()
    {{
        moveInput.x = Input.GetAxisRaw("Horizontal");
        moveInput.y = Input.GetAxisRaw("Vertical");
        moveInput = moveInput.normalized;
        {maybe('if (Input.GetKey(KeyCode.LeftShift)) moveInput *= sprintMultiplier;')}
    }}

    private void FixedUpdate()
    {{
        rb.MovePosition(rb.position + moveInput * (moveSpeed * Time.fixedDeltaTime));
    }}
}}
'''


def topdown():
    cls = pick('topdown'); sp = val(6)
    return f'''using UnityEngine;
using UnityEngine.InputSystem;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private float speed = {sp}f;
    [SerializeField] private float boundaryPadding = {random.choice([0.5,1,1.5])}f;
    private Camera mainCamera;

    private void Start()
    {{
        mainCamera = Camera.main;
    }}

    private void Update()
    {{
        Vector2 dir = ReadMove();
        if (dir.sqrMagnitude > 1f) dir.Normalize();
        transform.Translate(dir * (speed * Time.deltaTime));
        ClampToScreen();
    }}

    private Vector2 ReadMove()
    {{
        var kb = Keyboard.current;
        var dir = Vector2.zero;
        if (kb == null) return dir;
        if (kb.wKey.isPressed) dir.y += 1f;
        if (kb.sKey.isPressed) dir.y -= 1f;
        if (kb.aKey.isPressed) dir.x -= 1f;
        if (kb.dKey.isPressed) dir.x += 1f;
        return dir;
    }}

    private void ClampToScreen()
    {{
        if (mainCamera == null) return;
        Vector3 p = mainCamera.WorldToViewportPoint(transform.position);
        p.x = Mathf.Clamp01(p.x);
        p.y = Mathf.Clamp01(p.y);
        transform.position = mainCamera.ViewportToWorldPoint(p);
    }}
}}
'''


def projectile():
    cls = pick('projectile'); sp = random.choice([8, 10, 12, 15])
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private float speed = {sp}f;
    [SerializeField] private float destroyTime = {random.choice([2,3,4])}f;
    [SerializeField] private int damage = {random.choice([1,5,10,25])};

    private void Start()
    {{
        Destroy(gameObject, destroyTime);
    }}

    private void Update()
    {{
        transform.Translate(speed * Time.deltaTime * Vector3.up);
    }}

    private void OnTriggerEnter2D(Collider2D other)
    {{
        if (!other.CompareTag("Enemy")) return;
        other.SendMessage("TakeDamage", damage, SendMessageOptions.DontRequireReceiver);
        Destroy(gameObject);
    }}
}}
'''


def homing():
    cls = pick('homing'); sp = val(5)
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private float speed = {sp}f;
    [SerializeField] private float destroyTime = 5f;
    [SerializeField] private float turnSpeed = {random.choice([90,180,360])}f;
    [SerializeField] private Transform target;

    private void Start()
    {{
        Destroy(gameObject, destroyTime);
        FindNearestEnemy();
    }}

    private void Update()
    {{
        if (target == null)
        {{
            FindNearestEnemy();
            return;
        }}
        Vector2 direction = ((Vector2)target.position - (Vector2)transform.position).normalized;
        transform.position += (Vector3)(direction * (speed * Time.deltaTime));
    }}

    private void FindNearestEnemy()
    {{
        GameObject[] enemies = GameObject.FindGameObjectsWithTag("Enemy");
        if (enemies.Length == 0) return;
        float shortest = Mathf.Infinity;
        Transform nearest = null;
        foreach (GameObject enemy in enemies)
        {{
            if (enemy == null) continue;
            float d = Vector2.Distance(transform.position, enemy.transform.position);
            if (d < shortest)
            {{
                shortest = d;
                nearest = enemy.transform;
            }}
        }}
        target = nearest;
    }}
}}
'''


def shooter():
    cls = pick('shooter'); rate = round(random.uniform(0.08, 0.4), 2)
    return f'''using UnityEngine;
using UnityEngine.InputSystem;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private GameObject bulletPrefab;
    [SerializeField] private Transform firePoint;
    [Header("발사 설정")]
    [SerializeField] private float fireRate = {rate}f;
    private float nextFireTime;

    private void Update()
    {{
        var kb = Keyboard.current;
        if (kb == null) return;
        if (kb.zKey.isPressed && Time.time >= nextFireTime)
        {{
            nextFireTime = Time.time + fireRate;
            Shoot();
        }}
    }}

    private void Shoot()
    {{
        if (bulletPrefab == null)
        {{
            Debug.LogWarning("Bullet Prefab이 없습니다.");
            return;
        }}
        Vector3 spawnPos = firePoint != null ? firePoint.position : transform.position;
        Instantiate(bulletPrefab, spawnPos, Quaternion.identity);
    }}
}}
'''


def health():
    cls = pick('health'); hp = random.choice([3, 5, 10, 100])
    return f'''using System;
using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private int maxHealth = {hp};
    public int currentHealth;
    public event Action OnDamaged;
    public event Action OnDied;

    private void Awake()
    {{
        currentHealth = maxHealth;
    }}

    public void TakeDamage(int amount)
    {{
        if (amount <= 0) return;
        currentHealth -= amount;
        OnDamaged?.Invoke();
        if (currentHealth <= 0)
        {{
            Die();
        }}
    }}

    private void Die()
    {{
        OnDied?.Invoke();
        Destroy(gameObject);
    }}
}}
'''


def manager():
    cls = pick('manager')
    return f'''using UnityEngine;
using UnityEngine.SceneManagement;

public class {cls} : MonoBehaviour
{{
    private static {cls} instance;
    public static {cls} Instance
    {{
        get
        {{
            if (instance == null)
            {{
                instance = FindFirstObjectByType<{cls}>();
            }}
            return instance;
        }}
    }}

    [SerializeField] private int scoreValue;
    private int score;

    private void Awake()
    {{
        if (instance != null && instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        instance = this;
        DontDestroyOnLoad(gameObject);
    }}

    public void AddScore(int amount)
    {{
        score += amount;
        Debug.Log($"Score: {{score}}");
    }}

    public void Restart()
    {{
        SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
    }}
}}
'''


def loader():
    cls = pick('loader')
    return f'''using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using TMPro;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private Slider progressBar;
    [SerializeField] private TextMeshProUGUI progressText;
    public static string nextSceneName;

    public static void LoadScene(string sceneName)
    {{
        nextSceneName = sceneName;
        SceneManager.LoadScene("Loading");
    }}

    private void Start()
    {{
        if (string.IsNullOrEmpty(nextSceneName))
        {{
            Debug.LogError("씬 이름이 없습니다.");
            return;
        }}
        StartCoroutine(LoadAsync());
    }}

    private IEnumerator LoadAsync()
    {{
        AsyncOperation op = SceneManager.LoadSceneAsync(nextSceneName);
        op.allowSceneActivation = false;
        while (!op.isDone)
        {{
            float progress = Mathf.Clamp01(op.progress / 0.9f);
            if (progressBar != null) progressBar.value = progress;
            if (progressText != null) progressText.text = $"LOADING {{(progress * 100f):F0}}%";
            if (progress >= 0.99f)
            {{
                op.allowSceneActivation = true;
            }}
            yield return null;
        }}
    }}
}}
'''


def button():
    cls = pick('button')
    return f'''using DG.Tweening;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private GameObject panel;
    private RectTransform rectTransform;

    private void Start()
    {{
        rectTransform = GetComponent<RectTransform>();
    }}

    public void OnPointerEnter(PointerEventData eventData)
    {{
        rectTransform.DOComplete();
        rectTransform.DOScale(Vector3.one * 1.15f, 0.2f);
    }}

    public void OnPointerExit(PointerEventData eventData)
    {{
        rectTransform.DOComplete();
        rectTransform.DOScale(Vector3.one, 0.2f);
    }}

    public void OpenPanel()
    {{
        panel.SetActive(true);
    }}

    public void StartGame()
    {{
        SceneManager.LoadScene("Game");
    }}
}}
'''


def asset():
    cls = pick('asset')
    return f'''using UnityEngine;

[CreateAssetMenu(fileName = "{cls}", menuName = "Game/{cls}", order = 1)]
public class {cls} : ScriptableObject
{{
    public string displayName;
    public int maxHealth;
    public float moveSpeed;
    public Sprite icon;
    public Sprite[] animationFrames;
    [TextArea] public string description;
}}
'''


def pickup():
    cls = pick('pickup'); amount = random.choice([1, 5, 10, 50])
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private int value = {amount};
    [SerializeField] private float rotateSpeed = {random.choice([45,90,180])}f;
    [SerializeField] private AudioClip pickupSound;

    private void Update()
    {{
        transform.Rotate(Vector3.forward, rotateSpeed * Time.deltaTime);
    }}

    private void OnTriggerEnter2D(Collider2D other)
    {{
        if (!other.CompareTag("Player")) return;
        var wallet = other.GetComponent<Wallet>();
        if (wallet != null)
        {{
            wallet.Add(value);
        }}
        if (pickupSound != null)
        {{
            AudioSource.PlayClipAtPoint(pickupSound, transform.position);
        }}
        Destroy(gameObject);
    }}
}}
'''


def camera():
    cls = pick('camera')
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private Transform target;
    [SerializeField] private float smoothSpeed = {round(random.uniform(2,8),1)}f;
    [SerializeField] private Vector3 offset = new Vector3(0f, 0f, -10f);

    private void LateUpdate()
    {{
        if (target == null) return;
        Vector3 desired = target.position + offset;
        transform.position = Vector3.Lerp(transform.position, desired, smoothSpeed * Time.deltaTime);
    }}

    public void SetTarget(Transform newTarget)
    {{
        target = newTarget;
    }}
}}
'''


def audio():
    cls = pick('audio')
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    private static {cls} instance;
    public static {cls} Instance => instance;

    [SerializeField] private AudioSource bgmSource;
    [SerializeField] private AudioSource sfxSource;
    [Range(0f, 1f)] public float masterVolume = 0.8f;

    private void Awake()
    {{
        if (instance != null && instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        instance = this;
        DontDestroyOnLoad(gameObject);
    }}

    public void PlaySfx(AudioClip clip)
    {{
        if (clip == null) return;
        sfxSource.PlayOneShot(clip, masterVolume);
    }}

    public void PlayBgm(AudioClip clip)
    {{
        bgmSource.clip = clip;
        bgmSource.loop = true;
        bgmSource.Play();
    }}
}}
'''


def spawner():
    cls = pick('spawner'); interval = round(random.uniform(1, 4), 1)
    return f'''using System.Collections;
using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private GameObject enemyPrefab;
    [SerializeField] private float spawnInterval = {interval}f;
    [SerializeField] private int maxEnemies = {random.choice([5,10,20])};
    private int spawnedCount;

    private void Start()
    {{
        StartCoroutine(SpawnLoop());
    }}

    private IEnumerator SpawnLoop()
    {{
        while (spawnedCount < maxEnemies)
        {{
            Spawn();
            yield return new WaitForSeconds(spawnInterval);
        }}
    }}

    private void Spawn()
    {{
        if (enemyPrefab == null) return;
        Vector3 pos = transform.position + (Vector3)Random.insideUnitCircle * 2f;
        Instantiate(enemyPrefab, pos, Quaternion.identity);
        spawnedCount++;
    }}
}}
'''


def enemy():
    cls = pick('enemy'); sp = val(2, 0.3)
    return f'''using UnityEngine;

public class {cls} : MonoBehaviour
{{
    private enum State {{ Idle, Chase, Attack }}

    [SerializeField] private float moveSpeed = {sp}f;
    [SerializeField] private float detectionRange = {random.choice([4,6,8])}f;
    [SerializeField] private float attackRange = 1f;
    [SerializeField] private int damage = 1;
    private Transform player;
    private State state;

    private void Start()
    {{
        GameObject p = GameObject.FindGameObjectWithTag("Player");
        if (p != null) player = p.transform;
    }}

    private void Update()
    {{
        if (player == null) return;
        float distance = Vector2.Distance(transform.position, player.position);
        if (distance <= attackRange)
        {{
            state = State.Attack;
        }}
        else if (distance <= detectionRange)
        {{
            state = State.Chase;
            transform.position = Vector2.MoveTowards(transform.position, player.position, moveSpeed * Time.deltaTime);
        }}
        else
        {{
            state = State.Idle;
        }}
    }}

    private void Attack()
    {{
        player.SendMessage("TakeDamage", damage, SendMessageOptions.DontRequireReceiver);
    }}
}}
'''


def pool():
    cls = pick('pool')
    return f'''using System.Collections.Generic;
using UnityEngine;

public class {cls} : MonoBehaviour
{{
    [SerializeField] private GameObject prefab;
    [SerializeField] private int initialSize = {random.choice([5,10,20])};
    private readonly Queue<GameObject> pool = new Queue<GameObject>();

    private void Awake()
    {{
        for (int i = 0; i < initialSize; i++)
        {{
            GameObject obj = Instantiate(prefab, transform);
            obj.SetActive(false);
            pool.Enqueue(obj);
        }}
    }}

    public GameObject Get(Vector3 position)
    {{
        if (pool.Count == 0)
        {{
            GameObject extra = Instantiate(prefab, transform);
            extra.SetActive(false);
            pool.Enqueue(extra);
        }}
        GameObject item = pool.Dequeue();
        item.transform.position = position;
        item.SetActive(true);
        return item;
    }}

    public void Return(GameObject item)
    {{
        item.SetActive(false);
        pool.Enqueue(item);
    }}
}}
'''


BUILDERS = [mover2d, topdown, projectile, homing, shooter, health, manager, loader,
            button, asset, pickup, camera, audio, spawner, enemy, pool]

count = 0
for b in BUILDERS:
    for i in range(320):
        code = b()
        name = f'{b.__name__}_{i:02d}.cs'
        (OUT / name).write_text(code, encoding='utf-8')
        count += 1

print(f'generated {count} scripts in {OUT}')
