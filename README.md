# 빈칸에만 스킬 — Skill RTM

> 스킬을 많이 붙이지 않습니다. 주인 없는 요구사항에만 붙입니다.

업무 brief를 Capability RTM으로 펼쳐 현재 Evidence가 없는 행에만 권리·정확 버전·호환성·시험 근거를 통과한 최소 Skill 집합을 배정하는 읽기 전용 Hermes/OpenClaw 호환 Candidate입니다.

## 1분 실행

Python 3.8+와 표준 라이브러리만 사용합니다.

```bash
python3 scripts/skill_rtm.py plan \
  --task references/demo-task.json \
  --catalog references/demo-catalog.json \
  --format markdown
```

예상 핵심 결과:

```text
선택된 Skill: 2 / catalog 12
KEEP 1 · ASSIGN 2 · TRIAL 1 · ORPHAN 1
외부 행동: 0
```

테스트:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_skill_rtm.py' -v
```

## 데모에서 볼 장면

- 이미 Evidence가 있는 요구사항은 `KEEP`
- exact version의 네 gate가 통과한 두 Skill만 `ASSIGN`
- 설명만 있고 실행 근거가 없는 후보는 `TRIAL`
- 안전한 후보가 없는 외부 게시 행은 `ORPHAN`
- 동일한 최소집합이 여럿이면 임의 선택하지 않고 `CONFLICT`
- catalog의 나머지 9개 Skill은 관련 없으므로 선택하지 않음

이미 모든 요구사항이 충족된 경우에는 Skill을 억지로 붙이지 않습니다.

```bash
python3 scripts/skill_rtm.py plan \
  --task references/demo-all-keep-task.json \
  --catalog references/demo-catalog.json \
  --format markdown
```

```text
이미 충족: 1개
사람 결정 필요: 0개
추가 Skill: 0개
```

## 안전 경계

- 자동 검색·설치·활성화·실행·게시 없음
- Skill 원문 자동 병합 없음
- Candidate catalog의 문구는 명령이 아니라 데이터
- rights=`CLEARED`, compatibility=`VERIFIED`, test=`PASS`, proof=`TESTED`가 모두 아니면 `ASSIGN` 금지
- `KEEP`은 실대상 `TARGET`에서 `VERIFIED`된 Evidence만 허용; fixture/demo Evidence로 현재 충족 주장 금지
- 모든 fixture는 이 데모를 위해 작성한 synthetic 데이터
- synthetic `ASSIGN`은 실제 제3자 Skill의 사용 허가나 업무 성과를 뜻하지 않음

## 파일

- `SKILL.md`: Agent가 따르는 전체 workflow와 경계
- `scripts/skill_rtm.py`: validator·최소 집합 선택·JSON/Markdown 출력
- `references/demo-task.json`: 자작 문서 업무 brief fixture
- `references/demo-all-keep-task.json`: 이미 충족된 행에 Skill을 추가하지 않는 golden fixture
- `references/demo-pmo-task.json`: 자작 PMO 기준선 fixture
- `references/demo-development-task.json`: 자작 개발 release fixture
- `references/demo-catalog.json`: 자작 12-Skill catalog fixture
- `tests/test_skill_rtm.py`: 10개 behavior test — happy path·Evidence 등급·0개 배정·fail-closed·snapshot digest·3-domain reuse·최소 집합·동률/충돌·renderer

## 선행 대비 한 줄

검색기는 관련 Skill을 찾고 Router는 하나를 고릅니다. Skill RTM은 전체 요구사항 중 **아직 주인이 없는 행**을 공개하고, 그 행만 메우는 최소 exact-version 집합을 Evidence와 함께 배정합니다.

## 라이선스

MIT. 실제 외부 공유·출품은 제작자의 최종 승인 후 수행합니다.
