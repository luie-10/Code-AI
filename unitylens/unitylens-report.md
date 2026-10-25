# Unity 코드 해석 리포트

- 파일: 10개
- 타입: 11개
- 생성: 2026-10-25 04:28

## 요약

| 타입 | 베이스 | 역할 | 필드 | 읽기 | 쓰기 | 이슈 |
|---|---|---|---|---|---|---|
| BulletMove | MonoBehaviour | 이동 제어 | 2 | 2 | 0 | 0 |
| HomingBullet | MonoBehaviour | 이동 제어 | 3 | 6 | 1 | 0 |
| IntroButton | MonoBehaviour | UI 이벤트 핸들러 | 3 | 7 | 2 | 3 |
| KeyAction | — | 열거형 상수 | 0 | 0 | 0 | 0 |
| KeyManager | MonoBehaviour | 싱글턴 매니저 | 2 | 19 | 1 | 2 |
| LoadingSceneManager | MonoBehaviour | 씬 전환/로딩 연출 | 4 | 16 | 1 | 2 |
| PlayerData | ScriptableObject | 데이터 에셋 | 8 | 3 | 0 | 1 |
| PlayerMove | MonoBehaviour | 이동 제어 | 2 | 4 | 2 | 0 |
| PlayerShooting | MonoBehaviour | 스폰/발사 컨트롤러 | 5 | 12 | 1 | 0 |
| TmiReader | MonoBehaviour | UI 텍스트 표시 | 2 | 1 | 0 | 1 |
| TmiText | ScriptableObject | 데이터 에셋 | 1 | 0 | 0 | 0 |

## BulletMove

`BulletMove.cs` L3–19 · `public class BulletMove : MonoBehaviour`

**역할**: 이동 제어 / 수명 관리

- 이동 제어 — Update에서 transform을 직접 갱신 (프레임 독립: Time.deltaTime)
- 수명 관리 — Destroy(gameObject, t)로 오브젝트 수명 예약

총알 프리팹에 붙는 최소 구성입니다. `Start`에서 `Destroy(gameObject, destroyTime)`으로 수명을 예약하고, `Update`마다 `transform.Translate(speed * Time.deltaTime * Vector3.up)`로 **로컬 +Y 방향**으로 이동합니다. `speed`는 Inspector에서 조절하는 직렬화 값(기본 10)이고, `destroyTime`은 기본값이 없어 Inspector에서 반드시 채워야 합니다(0이면 스폰 즉시 소멸). Translate는 오브젝트의 회전을 반영하므로, 총알을 발사 방향으로 회전시켜 스폰하면 그 방향으로 날아갑니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| speed | float | O | 1 | 0 | Update |
| destroyTime | float | O | 1 | 0 | Start |

### 메서드

- `Start()` L9 (Unity)
- `Update()` L15 (Unity)

## HomingBullet

`HomingBullet.cs` L4–59 · `public class HomingBullet : MonoBehaviour`

**역할**: 이동 제어 / 수명 관리

- 이동 제어 — Update에서 transform을 직접 갱신 (프레임 독립: Time.deltaTime)
- 수명 관리 — Destroy(gameObject, t)로 오브젝트 수명 예약

매 프레임 `target`을 검사해 없으면 `FindNearestEnemy()`로 **"Enemy" 태그 전체를 다시 검색**합니다. 타겟이 있으면 정규화한 방향을 `transform.position`에 직접 더하고(관성 없음), 없으면 위로 직진합니다. 구조는 단순하지만 적이 없을 때 `Update`마다 `FindGameObjectsWithTag`가 호출되어 GC·CPU 부담이 커집니다. 재탐색 쿨다운(0.2초)이나 적 등록 리스트로 바꾸는 편이 좋습니다. `target`이 파괴되면 Unity의 fake-null 덕분에 `target == null`이 참이 되어 재탐색으로 이어집니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| speed | float | O | 2 | 0 | Update |
| destroyTime | float | O | 1 | 0 | Start |
| target | Transform | O | 3 | 1 | Update, FindNearestEnemy |

### 메서드

- `Start()` L10 (Unity)
- `Update()` L16 (Unity)
- `FindNearestEnemy()` L36

## IntroButton

`Intro Button.cs` L6–50 · `public class IntroButton : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler`

**역할**: UI 이벤트 핸들러

- UI 이벤트 핸들러 — EventSystem 인터페이스 구현: IPointerEnterHandler, IPointerExitHandler; OnPointerEnter/Exit에서 시각 반응 처리

EventTrigger 없이 `IPointerEnterHandler`/`IPointerExitHandler`를 직접 구현한 버튼입니다. DOTween으로 1.2배 ↔ 1.0배 스케일 트윈을 걸고, `DOComplete()`로 이전 트윈을 즉시 끝내 중첩을 막습니다. `originalX`에 시작 X 좌표를 저장하지만 **이후 읽는 곳이 없어 죽은 코드**입니다. `EditScene` 토글, `LoadingSceneManager.LoadScene("1_SlectScene")` 씬 이동, `Application.Quit()` + 에디터에서는 `isPlaying = false`로 재생 정지까지 처리합니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| EditScene | GameObject | O | 2 | 0 | EditSceneOn, EditSceneOff |
| rectTransform | RectTransform |  | 5 | 1 | Start, OnPointerEnter, OnPointerExit |
| originalX | float |  | 0 | 1 | Start |

### 메서드

- `Start()` L12 (Unity)
- `OnPointerEnter(PointerEventData eventData)` L18 (Unity)
- `OnPointerExit(PointerEventData eventData)` L25 (Unity)
- `EditSceneOn()` L31
- `EditSceneOff()` L35
- `StartScene()` L39
- `ExitGame()` L43

### 이슈

- **[high]** 파일명 ≠ 클래스명 — Unity는 MonoBehaviour의 파일명과 클래스명이 같아야 Inspector에서 컴포넌트로 붙일 수 있습니다. "IntroButton.cs"로 바꾸세요. (`Intro Button.cs ↔ IntroButton`)
- **[medium]** 쓰기만 하는 필드: originalX — 값을 저장하지만 어디에서도 읽지 않습니다. 죽은 코드이거나 로직 누락입니다. (`L10 · write 1 / read 0`)
- **[medium]** GetComponent 결과 null 미검사 — 컴포넌트가 없으면 다음 줄에서 NullReferenceException이 발생합니다. (RectTransform) (`L12 · Start`)

## KeyAction

`KeyInputManager.cs` L7–16 · `public enum KeyAction`

**역할**: 열거형 상수

- 열거형 상수 — 키/상태 값을 이름으로 묶은 enum (7개 항목)

## KeyManager

`KeyInputManager.cs` L18–106 · `public class KeyManager : MonoBehaviour`

**역할**: 싱글턴 매니저 / 입력 처리

- 싱글턴 매니저 — 정적 Instance 프로퍼티로 전역 접근점 제공; DontDestroyOnLoad로 씬 전환에도 유지
- 입력 처리 — Input System(Keyboard/Gamepad)에서 입력을 읽어 이동/공격으로 변환

Input System의 `Key` 열거형으로 **리바인딩 가능한 키맵**을 만드는 싱글턴입니다. 정적 `Instance` 프로퍼티가 없으면 `FindFirstObjectByType`으로 찾고, 그래도 없으면 `KeyManager` 오브젝트를 만들어 `DontDestroyOnLoad`로 유지합니다. `Awake`에서는 중복 인스턴스를 파괴합니다. `ChangeKey`는 코루틴을 띄워 `anyKey.wasPressedThisFrame`을 기다린 뒤 `Enum.GetValues(typeof(Key))`를 순회해 눌린 키를 찾아 `keys`에 덮어쓰고 콜백을 호출합니다. `keys`가 public이라 `PlayerMove`/`PlayerShooting`이 `TryGetValue`로 읽고, 없으면 기본 키로 폴백합니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| instance | KeyManager |  | 2 | 1 | Awake |
| keys | Dictionary<KeyAction,Key> | O | 17 | 0 | Awake, InitDefaultKeys, WaitForKeyPress, ReadMove, Update |

### 메서드

- `Awake()` L43 (Unity)
- `InitDefaultKeys()` L60
- `ChangeKey(KeyAction actionToRebind, Action<Key> onKeyRebound)` L73
- `WaitForKeyPress(KeyAction actionToRebind, Action<Key> onKeyRebound)` L78

### 이슈

- **[high]** 파일명 ≠ 클래스명 — Unity는 MonoBehaviour의 파일명과 클래스명이 같아야 Inspector에서 컴포넌트로 붙일 수 있습니다. "KeyManager.cs"로 바꾸세요. (`KeyInputManager.cs ↔ KeyManager`)
- **[low]** 정적 상태 유지 — static 필드는 씬을 넘어 값이 남습니다. 씬 재진입 시 초기화 시점을 명시하세요. (`L20 · static instance`)

## LoadingSceneManager

`Loading Manager.cs` L7–83 · `public class LoadingSceneManager : MonoBehaviour`

**역할**: 씬 전환/로딩 연출 / UI 텍스트 표시

- 씬 전환/로딩 연출 — SceneManager로 비동기 로드; 진행률을 UI에 반영
- UI 텍스트 표시 — TMP 컴포넌트의 text를 코드에서 갱신

정적 `nextSceneName`에 목표 씬을 저장하고 **"0.5_Loading" 씬으로 먼저 이동**합니다. 그 씬의 `Start`에서 `LoadSceneAsync`를 시작하고 `allowSceneActivation = false`로 90%에서 멈춰 둡니다. `op.progress / 0.9`를 Slider와 TMP 텍스트에 반영하고, 90% 이후에는 `fadeOrMinDelay` 동안 `Mathf.Lerp`로 게이지를 1까지 채운 뒤에야 씬 활성화를 허용합니다. 로딩이 너무 빨라 화면이 튀는 것을 막는 연출 장치입니다. `nextSceneName`이 비어 있으면 LogError 후 return합니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| progressBar | Slider | O | 8 | 0 | LoadSceneAsync |
| progressText | TextMeshProUGUI | O | 4 | 0 | LoadSceneAsync |
| fadeOrMinDelay | float | O | 2 | 0 | LoadSceneAsync |
| nextSceneName | string |  | 2 | 1 | LoadScene, Start, LoadSceneAsync |

### 메서드

- `LoadScene(string sceneName)` L23
- `Start()` L29 (Unity)
- `LoadSceneAsync()` L40

### 이슈

- **[high]** 파일명 ≠ 클래스명 — Unity는 MonoBehaviour의 파일명과 클래스명이 같아야 Inspector에서 컴포넌트로 붙일 수 있습니다. "LoadingSceneManager.cs"로 바꾸세요. (`Loading Manager.cs ↔ LoadingSceneManager`)
- **[low]** 정적 상태 유지 — static 필드는 씬을 넘어 값이 남습니다. 씬 재진입 시 초기화 시점을 명시하세요. (`L17 · static nextSceneName`)

## PlayerData

`Player.cs` L3–15 · `public class PlayerData : ScriptableObject`

**역할**: 데이터 에셋

- 데이터 에셋 — ScriptableObject를 상속 → 씬에 붙지 않는 데이터 에셋; CreateAssetMenu로 Project 창에서 .asset 생성 가능

`ScriptableObject` 데이터 컨테이너입니다. `CreateAssetMenu`로 Project 창에서 `.asset` 파일을 만들 수 있습니다. 이름·ID·체력·속도·아이콘·애니메이션 스프라이트·설명을 담고, `PlayerMove`가 `SelectScene.SelectedData`를 통해 이 값을 읽습니다. `chddkf`는 `GameObject` 필드인데 이름이 오타로 보이고 코드 어디에서도 참조되지 않습니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| playerName | string | O | 0 | 0 |  |
| playerID | int | O | 0 | 0 |  |
| playerHealth | int | O | 0 | 0 |  |
| playerSpeed | float | O | 1 | 0 | Start |
| chddkf | GameObject | O | 0 | 0 |  |
| playerIcon | Sprite | O | 2 | 0 | Start |
| playerAnimation | Sprite[] | O | 0 | 0 |  |
| playerDescription | string | O | 0 | 0 |  |

### 이슈

- **[low]** 의미를 알 수 없는 필드명: chddkf — 오타이거나 실험용 필드로 보입니다. 이름을 의도에 맞게 바꾸세요. (`L11 · GameObject`)

## PlayerMove

`PlayerMove.cs` L4–88 · `public class PlayerMove : MonoBehaviour`

**역할**: 이동 제어 / 화면 경계 제한

- 이동 제어 — Update에서 transform을 직접 갱신 (프레임 독립: Time.deltaTime)
- 화면 경계 제한 — 카메라 뷰포트 좌표로 위치를 Clamp

`SelectScene.SelectedData`(외부 정적 참조)에서 `playerSpeed`를 읽어 `speed = playerSpeed * 5`로 만들고, `playerIcon`을 `SpriteRenderer.sprite`에 적용합니다. `Update`에서는 키보드(`KeyManager`의 바인딩, 기본 WASD)와 게임패드 스틱·DPad를 합산해 방향을 만들고, 대각선일 때 정규화한 뒤 이동합니다. 마지막에 카메라 뷰포트 좌표로 위치를 Clamp해 화면 밖으로 나가지 못하게 합니다. **선택 데이터가 없으면 `speed = 0`이라 캐릭터가 움직이지 않습니다** — 기본 속도 폴백이 필요합니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| speed | float |  | 1 | 1 | Start, Update |
| mainCamera | Camera |  | 3 | 1 | Start, ClampToBounds |

### 메서드

- `Start()` L10 (Unity)
- `Update()` L32 (Unity)
- `ClampToBounds()` L42
- `ReadMove()` L54

## PlayerShooting

`PlayerShooting.cs` L4–73 · `public class PlayerShooting : MonoBehaviour`

**역할**: 스폰/발사 컨트롤러 / 이동 제어

- 스폰/발사 컨트롤러 — Instantiate로 프리팹을 런타임 생성; fireRate로 연사 간격 제어
- 이동 제어 — Update에서 transform을 직접 갱신 (프레임 독립: Time.deltaTime)

매 프레임 `KeyManager`에서 Attack/Ultimate 키를 조회하고(없으면 Z/X) 공격을 처리합니다. 기본 공격은 `isPressed` + `nextFireTime` 쿨다운으로 연사하고, 필살기는 `wasPressedThisFrame`으로 단발 발사합니다. 스폰 위치는 `firePoint`가 있으면 그곳, 없으면 자기 위치입니다. `homingbulletPrefab`이 비어 있으면 일반 총알로 대체하고 경고를 남기는 방어 코드가 들어 있습니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| bulletPrefab | GameObject | O | 3 | 0 | Shoot, HomingShoot |
| homingbulletPrefab | GameObject | O | 3 | 0 | HomingShoot |
| firePoint | Transform | O | 4 | 0 | Shoot, HomingShoot |
| fireRate | float | O | 1 | 0 | Update |
| nextFireTime | float |  | 1 | 1 | Update |

### 메서드

- `Update()` L14 (Unity)
- `Shoot()` L43
- `HomingShoot()` L55

## TmiReader

`TmiReader.cs` L4–13 · `public class TmiReader : MonoBehaviour`

**역할**: UI 텍스트 표시

- UI 텍스트 표시 — TMP 컴포넌트의 text를 코드에서 갱신

`tmiText` 배열에서 `Random.Range(0, Length)`로 한 항목을 골라 TMP에 `TMI : ...` 형식으로 출력합니다. 배열이 비어 있으면 `Random.Range(0, 0)`이 0을 반환해 `[0]` 접근에서 **IndexOutOfRangeException**이 납니다. `Start`에서 한 번만 실행되므로 씬마다 한 줄이 랜덤으로 보입니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| tmiText | TmiText[] | O | 0 | 0 |  |
| Tmitext | TextMeshProUGUI | O | 1 | 0 | Start |

### 메서드

- `Start()` L9 (Unity)

### 이슈

- **[medium]** 빈 배열 인덱스 위험 — 배열이 비어 있으면 Random.Range(0,0)=0 → [0] 접근에서 IndexOutOfRangeException. Length 검사를 추가하세요. (`L9`)

## TmiText

`TmiText.cs` L3–9 · `public class TmiText : ScriptableObject`

**역할**: 데이터 에셋

- 데이터 에셋 — ScriptableObject를 상속 → 씬에 붙지 않는 데이터 에셋; CreateAssetMenu로 Project 창에서 .asset 생성 가능

TMI 한 줄을 담는 `ScriptableObject`입니다. 다만 `CreateAssetMenu`의 `fileName`이 **"PlayerData"로 PlayerData와 중복**입니다. 에셋을 만들 때 파일명이 겹치므로 `TmiData` 등으로 바꾸는 편이 안전합니다.

### 필드

| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |
|---|---|---|---|---|---|
| Tmi | string | O | 0 | 0 |  |

## 미해석 외부 참조

- `UnityEditor` ← IntroButton L47
- `SelectScene` ← PlayerMove L13