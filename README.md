# インカの黄金 (Inca Gold / Diamant) ゲームロジック

オンライン対戦ボードゲーム「インカの黄金」のサーバーサイド・ゲームエンジンおよびルール実装です。Web層・CPU・観戦機能等は除外し、純粋なゲームエンジンとテストのみを実装しています。

## 構成
- `gameplatform/`: 共通基盤（ルーム・セッション・リアルタイム通知など）
- `games/inca/`: インカの黄金のゲームロジック (`config.py`, `cards.py`, `engine.py`, `views.py`)
- `tests/`: ユニットテストスイート

## テストの実行方法
```bash
python -m unittest discover -s tests -t . -q
```
