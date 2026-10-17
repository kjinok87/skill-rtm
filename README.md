# 빈칸에만 스킬 — Skill RTM

**할 일은 빠짐없이 확인하고, 이미 해결된 일은 그대로 두고, 부족한 일에만 필요한 스킬을 추천합니다.**

AI에게 보고서나 개발 작업을 맡길 때 어떤 스킬이 필요한지 판단하기 어렵습니다. Skill RTM은 해야 할 일을 작은 항목으로 나누고, 이미 확인된 결과와 사용 가능한 스킬을 대조해 표로 정리합니다. RTM은 각 요구사항이 어떤 근거와 스킬에 연결되는지 추적하는 표를 뜻합니다.

> **0.2.0부터 비상업적 사용·공유만 허용합니다. 외부 상업용 사용, 판매, 유료 서비스 탑재, 유상 컨설팅·교육과 상업적 배포는 금지합니다.** [이용 조건 전문](LICENSE)

## 예를 들면

무료 학습 모임에서 보고서를 만든다고 가정해 보겠습니다.

| 해야 할 일 | 확인한 상황 | RTM이 알려주는 내용 |
|---|---|---|
| 제목 넣기 | 완성된 보고서의 제목을 확인함 | 이미 되어 있으니 유지 |
| 주장마다 출처 붙이기 | 아직 없고, 시험을 통과한 출처 확인 스킬이 있음 | 그 스킬을 추천 |
| 개인정보 지우기 | 검증된 개인정보 점검 스킬이 있음 | 그 스킬을 추천 |
| 압축파일 점검 | 관련 스킬 설명만 있고 실행 증거가 없음 | 시험·확인 필요 |
| 외부 게시 승인 받기 | 담당 스킬과 승인 근거가 없음 | 해결되지 않은 일로 표시 |

12개 스킬이 있어도 필요한 2개만 추천할 수 있습니다. 모든 일이 이미 확인됐다면 **추가 스킬 0개**가 정상입니다. 위 예시는 합성 데이터이며 실제 업무를 검증한 결과가 아닙니다.

## 결과 표 읽는 법

| 표시 | 쉬운 뜻 | 다음 할 일 |
|---|---|---|
| `KEEP` | 현재 결과를 확인할 증거가 있음 | 유지 |
| `ASSIGN` | 조건을 통과한 스킬을 추천함 | 배치안 검토. 아직 실행한 것은 아님 |
| `TRIAL` | 후보는 있지만 확인이 부족함 | 권리·호환성·시험 근거 보완 |
| `CONFLICT` | 후보 조합이 충돌하거나 같은 최선의 조합이 여러 개임 | 사람의 결정 필요 |
| `ORPHAN` | 연결할 후보가 없음 | 사람이 처리하거나 요구사항 재검토 |

추천에는 스킬의 **정확한 버전, 사용할 권리, 실행 환경 호환성, 시험 결과와 해당 요구사항을 해결한 근거**가 필요합니다. 이름이나 설명만으로 통과시키지 않습니다. 같은 범위를 해결한다면 더 적은 수의 스킬을 고릅니다.

## 무엇을 준비하나요?

1. **해야 할 일:** 요구사항과 완료 기준.
2. **이미 한 일의 증거:** 산출물, 실행 로그, 시험 결과와 확인 가능한 위치.
3. **후보 스킬:** 정확한 버전, 출처와 검증 자료.
4. **사용 목적:** 비상업적 사용임을 확인하고 현재 이용 조건에 동의한 기록.

입력에 적힌 근거의 진실성까지 대신 확인하지는 않습니다. 확인하지 않은 자료를 `VERIFIED`나 `TESTED`로 표시하면 안 됩니다.

## 바로 사용하기

- **문서로 사용:** [이관용 MD](HANDOFF.md)를 AI에 첨부하고 업무와 증거를 함께 전달하세요. MD만으로 작성한 결과는 수동 분석안입니다.
- **자동 계산:** 저장소 전체를 `Code → Download ZIP`으로 받거나 아래처럼 복제하세요. Python 3.8 이상이면 되고 추가 패키지는 필요 없습니다.

```bash
git clone https://github.com/kjinok87/skill-rtm.git
cd skill-rtm
python3 -B scripts/skill_rtm.py plan --task references/demo-task.json --catalog references/demo-catalog.json --format markdown
```

Windows PowerShell에서는 다음과 같이 실행합니다.

```powershell
git clone https://github.com/kjinok87/skill-rtm.git
Set-Location '.\skill-rtm'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B scripts/skill_rtm.py plan --task references/demo-task.json --catalog references/demo-catalog.json --format markdown
```

기본 출력은 JSON입니다. `--format markdown`을 붙이면 같은 결과를 표로 보여줍니다. 예시 실행의 예상 결과는 `KEEP 1 / ASSIGN 2 / TRIAL 1 / CONFLICT 0 / ORPHAN 1`입니다.

## 상업용 요청은 어떻게 막나요?

**이용 조건, AI 지시문, 실행 코드에 같은 제한을 적용합니다.**

- [LICENSE](LICENSE): 이 버전의 상업적 사용·배포를 허락하지 않습니다. 비상업적 공유에도 저작권과 이 조건을 유지해야 합니다.
- [SKILL.md](SKILL.md): AI가 상업용 전환·판매·유료 서비스 탑재·상업적 배포나 그 우회 요청을 받으면 지원을 중단하도록 규정합니다.
- [실행 코드](scripts/skill_rtm.py): 사용 목적과 동의 기록을 확인한 뒤 계산합니다. 상업용·미확인·미동의·누락 입력은 `FAIL`과 종료코드 `1`로 중단하며 배치안을 만들지 않습니다.

실제 업무의 task JSON에는 다음 항목을 넣어야 합니다. 실제 목적이 비상업적이고 조건을 읽고 동의한 경우에만 작성하세요.

```json
{
  "schema_version": 2,
  "usage_policy": {
    "license_id": "LicenseRef-Skill-RTM-NonCommercial-1.0",
    "accepted": true,
    "use": "NONCOMMERCIAL",
    "distribution": "NONE"
  }
}
```

위 코드는 전체 task가 아닌 추가할 필드의 예시입니다. 나머지 구조는 [작업 예시](references/demo-task.json)를 참고하세요. `distribution`은 배포하지 않으면 `NONE`, 무상 비상업적 공유이면 `NONCOMMERCIAL`입니다. 카탈로그의 `schema_version`은 기존 정수 `1`을 사용합니다. 이전 task 형식 `1`은 자동으로 동의 처리하지 않으며 새 목적 확인이 필요합니다.

**차단 범위도 분명히 합니다.** 이 검사는 입력자가 밝힌 목적을 확인하는 실행 관문입니다. 실제 수익 활동을 감시하거나 허위 신고·코드 수정을 완전히 막는 DRM은 아닙니다. 입력값만 바꿔 상업용으로 쓰면 허가되는 것이 아닙니다.

이전 MIT 공개 버전과 이미 전달된 사본의 권리를 이번 변경으로 소급 취소할 수는 없습니다. 현재 조건은 **0.2.0과 그 조건을 표시하는 후속 버전**에 적용합니다. 과거 사본을 회수하거나 Git 이력을 지워 권리가 사라졌다고 주장하지 않습니다. 기존 MIT 조건은 [변경 전 LICENSE](https://github.com/kjinok87/skill-rtm/blob/0068065e20747c5914002944fa611fbb89f2fd5f/LICENSE)에서 확인할 수 있습니다. 라이선스 변경의 일반적인 고려 사항은 [GitHub의 설명](https://opensource.guide/legal/#what-if-i-want-to-change-the-license-of-my-project)을 참고하세요.

## 하지 않는 일

스킬 자동 설치·실행, 파일 외부 전송, 결제, 실제 배포 또는 공식 인수 승인을 수행하지 않습니다. `PASS`는 표 계산이 끝났다는 뜻이며 업무 성공이나 운영 준비 완료를 뜻하지 않습니다.

## 시험과 파일 안내

```powershell
python -B -m unittest discover -s tests -p test_skill_rtm.py -v
```

Windows에서는 위 실행 예시의 UTF-8 환경변수를 먼저 설정하세요.

| 파일 | 용도 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 다른 분에게 전달하는 사용 안내와 전체 지시문 |
| [SKILL.md](SKILL.md) | AI가 따라야 할 스킬 규칙 |
| [scripts/skill_rtm.py](scripts/skill_rtm.py) | 입력 검사와 최소 스킬 집합 계산 |
| [references](references) | 합성 작업·카탈로그 예시 |
| [tests/test_skill_rtm.py](tests/test_skill_rtm.py) | 계산, 입력 경계와 비상업용 차단 회귀 검사 |
| [LICENSE](LICENSE) | 비상업용 이용 조건 전문 |

저작권자: Kuni. 현재 버전은 비상업적 이용만 허용하는 소스 공개 자료이며, 상업적 사용을 허용하는 오픈소스 라이선스로 표시하지 않습니다.
