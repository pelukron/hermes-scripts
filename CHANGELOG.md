# Changelog

Todos los cambios notables se documentan aqui. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.5] - 2026-09-15

## v0.17.1 (2026-09-25)

### 🐛 Fixes

- El digest de drift en --quiet calla ante extras informativos
  ([`baa52db`](https://github.com/pelukron/hermes-scripts/commit/baa52db1d8a531d78ced0bb65bfac2f44e05f4f8))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`9fde4fc`](https://github.com/pelukron/hermes-scripts/commit/9fde4fc6fdb46ee1ec3fe6d1aae3ee4c0d523280))


## v0.17.0 (2026-09-25)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e0b3466`](https://github.com/pelukron/hermes-scripts/commit/e0b34666a16b2f915da1de0b246cbce237316a99))

### ✨ Features

- Ledger de anomalias nocturnas que abre un ticket deduplicado
  ([`1e78f89`](https://github.com/pelukron/hermes-scripts/commit/1e78f8923a901fdf2093dcefdd0c56d89774370e))


## v0.16.18 (2026-09-25)

### 🐛 Fixes

- Las notas del release ya no listan el mismo cambio dos veces
  ([#296](https://github.com/pelukron/hermes-scripts/pull/296),
  [`9df50ab`](https://github.com/pelukron/hermes-scripts/commit/9df50ab6fe8b0b154479c109aa12517e21aee6dd))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`17b16d6`](https://github.com/pelukron/hermes-scripts/commit/17b16d60f02bb0245030d3a8ade064f733e21258))


## v0.16.17 (2026-09-25)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`da4d9ff`](https://github.com/pelukron/hermes-scripts/commit/da4d9ffd8d08448621e5a9218f8b63d13ad56849))

### 📝 Docs

- La skill del flujo pelukron registra que el push va antes del merge
  ([#295](https://github.com/pelukron/hermes-scripts/pull/295),
  [`6d4f976`](https://github.com/pelukron/hermes-scripts/commit/6d4f976f2d6e81c526fd7252586f5bb6befd7b5b))

- La skill del flujo pelukron registra que el push va antes del merge
  ([#294](https://github.com/pelukron/hermes-scripts/pull/294),
  [`b6cf27b`](https://github.com/pelukron/hermes-scripts/commit/b6cf27b78a06f2e618212693c96955a4a7a876d2))


## v0.16.16 (2026-09-24)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`3af8299`](https://github.com/pelukron/hermes-scripts/commit/3af8299b856188a95b201ac38b4e7b1beef315be))

### 🔧 Infra

- El gate afirma las versiones pinneadas
  ([#293](https://github.com/pelukron/hermes-scripts/pull/293),
  [`61e0209`](https://github.com/pelukron/hermes-scripts/commit/61e020932084d103463e7fdc05538744d04f4c7c))


## v0.16.15 (2026-09-24)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`6f010c3`](https://github.com/pelukron/hermes-scripts/commit/6f010c36b4fe7a9267be62391c951471bbd82762))

### 📝 Docs

- La skill del flujo pelukron aprende que el ruleset fija los nombres de los checks (#291)
  ([#292](https://github.com/pelukron/hermes-scripts/pull/292),
  [`bce19eb`](https://github.com/pelukron/hermes-scripts/commit/bce19ebca8e7d2b78b29a469a605cbecae921f9c))


## v0.16.14 (2026-09-24)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`692d3ee`](https://github.com/pelukron/hermes-scripts/commit/692d3eebeddb87e57248bb73c4d6655823f75ebf))

### 🔧 Infra

- El gate es un solo comando en local, CI y la noche (#265)
  ([#290](https://github.com/pelukron/hermes-scripts/pull/290),
  [`8b035c2`](https://github.com/pelukron/hermes-scripts/commit/8b035c25fd81cba401d3cfb3a077f040d0f7722f))


## v0.16.13 (2026-09-24)

### 🐛 Fixes

- Gh y uv se resuelven por ruta absoluta, no por nombre relativo
  ([`ea9ef9e`](https://github.com/pelukron/hermes-scripts/commit/ea9ef9e7a821a1f52c93395b4de3488490587081))

- Gh y uv se resuelven por ruta absoluta, y un guard lo sostiene (#256)
  ([#289](https://github.com/pelukron/hermes-scripts/pull/289),
  [`9fd740b`](https://github.com/pelukron/hermes-scripts/commit/9fd740b0920e6d1646068644512b23d053c591a2))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`19d6b64`](https://github.com/pelukron/hermes-scripts/commit/19d6b645e34873a9ab85bbf12b5458fff1794223))

### ✅ Tests

- El PATH de las pruebas de resolutores no puede ser /usr/bin:/bin
  ([`6a0c445`](https://github.com/pelukron/hermes-scripts/commit/6a0c44511c2219445946781d8a086eb053931572))

- Guard para que src/ no invoque herramientas externas por nombre relativo
  ([`1c89316`](https://github.com/pelukron/hermes-scripts/commit/1c89316961ba004dc7e1b42d1ed4c58dd2a846c3))


## v0.16.12 (2026-09-24)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`b3849f9`](https://github.com/pelukron/hermes-scripts/commit/b3849f9e95efe21c2ee5d9b8ba9d707c3e1eaa34))

### 🔧 Infra

- La excepcion de click se muda al audit
  ([#288](https://github.com/pelukron/hermes-scripts/pull/288),
  [`14bbdd4`](https://github.com/pelukron/hermes-scripts/commit/14bbdd446a34373f8859304444f8dfb22b78bb0f))

- La excepcion de click vive en el audit, no en el resolver
  ([`ec750c7`](https://github.com/pelukron/hermes-scripts/commit/ec750c7954e2a448c2dddf1015f8d8ae158754b5))

- Python-semantic-release vuelve a 10.6.2 y fuera el guard de click
  ([`44c36e7`](https://github.com/pelukron/hermes-scripts/commit/44c36e735c297e3282fe08c078900c5756697e48))


## v0.16.11 (2026-09-24)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`0f69ee7`](https://github.com/pelukron/hermes-scripts/commit/0f69ee7507da2e1f39d2659f33be11794e393736))

- **deps**: Bump github/codeql-action from 4.37.3 to 4.38.1
  ([#286](https://github.com/pelukron/hermes-scripts/pull/286),
  [`10f6fef`](https://github.com/pelukron/hermes-scripts/commit/10f6fef04a2de34d36f25ef3eac10a1d0b416f53))

- **deps**: Bump github/codeql-action from 4.37.3 to 4.38.1
  ([`f3b9ebf`](https://github.com/pelukron/hermes-scripts/commit/f3b9ebfdd25d951196651b30ec1a4623efe01c50))


## v0.16.10 (2026-09-23)

### 🐛 Fixes

- Volver a python-semantic-release 10.6.1
  ([#285](https://github.com/pelukron/hermes-scripts/pull/285),
  [`630f38c`](https://github.com/pelukron/hermes-scripts/commit/630f38c7f0b792d7a29e90041b6070d4b80be24d))

- Volver a python-semantic-release 10.6.1
  ([`2b208b1`](https://github.com/pelukron/hermes-scripts/commit/2b208b1f8b8360214e5153e121f4903b743ff6d1))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`7b5d0ac`](https://github.com/pelukron/hermes-scripts/commit/7b5d0ac03cfb1dca0b71cce1fe98e27796efc7b5))

- **deps-dev**: Bump python-semantic-release from 10.6.1 to 10.6.2
  ([#264](https://github.com/pelukron/hermes-scripts/pull/264),
  [`f8055d4`](https://github.com/pelukron/hermes-scripts/commit/f8055d4452b989609e1afe6a4b04015c0c556108))

- **deps-dev**: Bump python-semantic-release from 10.6.1 to 10.6.2
  ([`2117c07`](https://github.com/pelukron/hermes-scripts/commit/2117c0775c455b653443e76cfadfdc37fbba99b3))


## v0.16.9 (2026-09-23)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`5fd9922`](https://github.com/pelukron/hermes-scripts/commit/5fd99222fa50fbf1bf4d96b14b8c35f70edd1efc))

### 📝 Docs

- AGENTS.md con el entorno del gate y las reglas de entrega de reportes
  ([#282](https://github.com/pelukron/hermes-scripts/pull/282),
  [`4058319`](https://github.com/pelukron/hermes-scripts/commit/405831989d5d0fd1efec6deb6e8d29e5faca40ef))


## v0.16.8 (2026-09-23)

### 🐛 Fixes

- El corte del diario no puede partir un enlace
  ([#278](https://github.com/pelukron/hermes-scripts/pull/278),
  [`45fff64`](https://github.com/pelukron/hermes-scripts/commit/45fff64620180d3c33bced2bae0da139ed617852))

- El corte del diario parte la URL y pierde el diseño
  ([#278](https://github.com/pelukron/hermes-scripts/pull/278),
  [`159c1a4`](https://github.com/pelukron/hermes-scripts/commit/159c1a4073512cc5aa01aa3579e93fc1a43a3c53))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`015e3ab`](https://github.com/pelukron/hermes-scripts/commit/015e3abc2047fb80d31988010977a72662f9de28))

### 📝 Docs

- El corte puede dejar un bullet huérfano de su item
  ([#278](https://github.com/pelukron/hermes-scripts/pull/278),
  [`87bd069`](https://github.com/pelukron/hermes-scripts/commit/87bd069c33dde58323faea097c4923c7b2236f0f))

- El presupuesto de entrega es por mensaje, no por corrida
  ([#278](https://github.com/pelukron/hermes-scripts/pull/278),
  [`7a0b78c`](https://github.com/pelukron/hermes-scripts/commit/7a0b78cdf04c94f93208b9f4f2cb862baf712c86))


## v0.16.7 (2026-09-23)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`d8ddbaf`](https://github.com/pelukron/hermes-scripts/commit/d8ddbafe2398d0e927ab292b8405660979c999c0))

### 📝 Docs

- Uv run dentro del clon de runtime rompe el ff-only del job
  ([#277](https://github.com/pelukron/hermes-scripts/pull/277),
  [`b49f7e3`](https://github.com/pelukron/hermes-scripts/commit/b49f7e3b584fbb4745a8c5e0cf92e60b48a32a6a))

- Uv run dentro del clon de runtime rompe el ff-only del job
  ([`9672a9b`](https://github.com/pelukron/hermes-scripts/commit/9672a9bcc1ec922c5a412c03c8b77e7a3230bda1))


## v0.16.6 (2026-09-23)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`56c409a`](https://github.com/pelukron/hermes-scripts/commit/56c409a366a9ad2badedd60eb2ab45536070adbd))

### 📝 Docs

- Cómo dar de baja un job extra que no está en el manifiesto
  ([#275](https://github.com/pelukron/hermes-scripts/pull/275),
  [`34fad8e`](https://github.com/pelukron/hermes-scripts/commit/34fad8e8a69984fddb0d4c12f93e1c022cb70d22))

- Cómo dar de baja un job extra que no está en el manifiesto
  ([`b5737e2`](https://github.com/pelukron/hermes-scripts/commit/b5737e251ba8a17af4925d615b5fd32b4cbfc586))


## v0.16.5 (2026-09-23)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`0fc9754`](https://github.com/pelukron/hermes-scripts/commit/0fc97549a9748cb36625e7cf543b8e95ce898dc5))

### 📝 Docs

- Los tres rojos locales del gate (PATH de uv, TMPDIR de pytest y /tmp tmpfs)
  ([#273](https://github.com/pelukron/hermes-scripts/pull/273),
  [`1d11d1f`](https://github.com/pelukron/hermes-scripts/commit/1d11d1f565ad0222d0a89882fefecd331e127e6c))

- Los tres rojos locales del gate (PATH de uv, TMPDIR de pytest y /tmp tmpfs)
  ([`2a90444`](https://github.com/pelukron/hermes-scripts/commit/2a904443130411116b446287b8e5e7c2a45df294))


## v0.16.4 (2026-09-23)

### 🐛 Fixes

- El sandbox del smoke se libra de B108 con nosec
  ([`b2b1834`](https://github.com/pelukron/hermes-scripts/commit/b2b1834046af5fea63cbc525239c61b77e320c10))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`015516a`](https://github.com/pelukron/hermes-scripts/commit/015516a02466c414f60a52099374180137155b80))

### 🔧 Infra

- El wrapper exporta el PATH de uv y el instalador puede probar un job
  ([#269](https://github.com/pelukron/hermes-scripts/pull/269),
  [`429f790`](https://github.com/pelukron/hermes-scripts/commit/429f79069709d9bbf52d367dbf037406b1c2cc8f))


## v0.16.3 (2026-09-23)

### 🐛 Fixes

- El smoke de runtime-sync falla con rc=127 bajo el PATH del cron
  ([#271](https://github.com/pelukron/hermes-scripts/pull/271),
  [`fd27d50`](https://github.com/pelukron/hermes-scripts/commit/fd27d50f91d716d04e8c6e57fcf4653bdd5d5a13))

- El smoke de runtime-sync falla con rc=127 bajo el PATH del cron
  ([`7d9d940`](https://github.com/pelukron/hermes-scripts/commit/7d9d9403d0778794512ebd4fa43c38554c70857d))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`332b1e9`](https://github.com/pelukron/hermes-scripts/commit/332b1e92e009d5d4196f96f590cfda8dfac0d001))


## v0.16.2 (2026-09-23)

### 🐛 Fixes

- La huella del canary ignora el latido del gateway
  ([#268](https://github.com/pelukron/hermes-scripts/pull/268),
  [`8cb8414`](https://github.com/pelukron/hermes-scripts/commit/8cb8414bbd4a5df8976b05f2c8596f38076f0ee0))

- La huella del canary ignora el latido del gateway
  ([`3314ef8`](https://github.com/pelukron/hermes-scripts/commit/3314ef8937dffa1f78cde971feadcd0882fb1f3f))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`96625ef`](https://github.com/pelukron/hermes-scripts/commit/96625efeddd3496c4cdae56832078bf286d5bcdf))


## v0.16.1 (2026-09-22)

### 🐛 Fixes

- Los jobs que invocan uv por nombre fallan en cron
  ([#255](https://github.com/pelukron/hermes-scripts/pull/255),
  [`0a7de6b`](https://github.com/pelukron/hermes-scripts/commit/0a7de6b79d139e358690e59f6dd06f79568512e2))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`f9b3f82`](https://github.com/pelukron/hermes-scripts/commit/f9b3f82e16cd6515e667136ced6fb2c778941624))


## v0.16.0 (2026-09-22)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`47e907e`](https://github.com/pelukron/hermes-scripts/commit/47e907e2c86ffbe14b9adc5a26e750f7bf5e5573))

### 📝 Docs

- El emoji de estado no va en el titulo del PR
  ([`7becbf5`](https://github.com/pelukron/hermes-scripts/commit/7becbf59244d07ee8b705759de03bf3990cfefb5))

- La skill del flujo dice la verdad sobre titulos de PR y helpers
  ([`5f8406d`](https://github.com/pelukron/hermes-scripts/commit/5f8406d6b183b4247ef5683a1827d1120e28eadc))

- La skill del flujo ya no manda verificar un job a mano
  ([`01240f8`](https://github.com/pelukron/hermes-scripts/commit/01240f8dceb008ef5d8ea984adbbc2151facae54))

### ✨ Features

- Las skills del sistema viven en el repo y las independientes se declaran
  ([#253](https://github.com/pelukron/hermes-scripts/pull/253),
  [`eda6802`](https://github.com/pelukron/hermes-scripts/commit/eda6802bbb22f1a1600cbea2b1f2bd98b148382b))

- Las skills del sistema viven en el repo y las independientes se declaran
  ([`d8b3457`](https://github.com/pelukron/hermes-scripts/commit/d8b3457daced7d6b11f3d381946d029ddf999efc))


## v0.15.0 (2026-09-22)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`9b820ef`](https://github.com/pelukron/hermes-scripts/commit/9b820efdfe7b7299f4f7908780afe74fa79d61d2))

### ✨ Features

- Auto-update de hermes-scripts y extras como drift
  ([#250](https://github.com/pelukron/hermes-scripts/pull/250),
  [`194bc43`](https://github.com/pelukron/hermes-scripts/commit/194bc43e3208e11da3ca4765f4f86876023e82b0))


## v0.14.0 (2026-09-22)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`dd59097`](https://github.com/pelukron/hermes-scripts/commit/dd59097227355d37f6c33b566978d778460e0532))

### ✨ Features

- Testigo externo para el cron de Hermes
  ([#249](https://github.com/pelukron/hermes-scripts/pull/249),
  [`e3c3506`](https://github.com/pelukron/hermes-scripts/commit/e3c3506c4ce81af3ea640dcad9a5c6d1c2d7ca1a))


## v0.13.0 (2026-09-22)

### 🐛 Fixes

- El gate del sha adoptado vuelve a verde
  ([`6eaab5c`](https://github.com/pelukron/hermes-scripts/commit/6eaab5c7496bb0c946edd94fa9b5bd88589cce44))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e61faf2`](https://github.com/pelukron/hermes-scripts/commit/e61faf27f8f1fa1d5064386f76a3cea8c4f04cde))

### ✨ Features

- Auditoria nocturna del sha adoptado ([#248](https://github.com/pelukron/hermes-scripts/pull/248),
  [`ce2605b`](https://github.com/pelukron/hermes-scripts/commit/ce2605b3ea948d95a113378490dfacf878c28ccd))


## v0.12.1 (2026-09-22)

### 🐛 Fixes

- El release lista los cambios que entran por PR
  ([#247](https://github.com/pelukron/hermes-scripts/pull/247),
  [`9479bc1`](https://github.com/pelukron/hermes-scripts/commit/9479bc139445d3798106ac463017f96152e2d36e))

- El release lista los cambios que entran por PR
  ([`22f3099`](https://github.com/pelukron/hermes-scripts/commit/22f309989ad23bcb4904a7e0b5656131ce9cafa1))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`040d90c`](https://github.com/pelukron/hermes-scripts/commit/040d90cb40ac9c2737b8c0749d327a72f14aab77))


## v0.12.0 (2026-09-21)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e46ffeb`](https://github.com/pelukron/hermes-scripts/commit/e46ffeb635ad44b5cec2e4044349770929a422b8))


## v0.11.6 (2026-09-21)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`793c6ea`](https://github.com/pelukron/hermes-scripts/commit/793c6ea9561c51e3c742d1a23f684d1d7497eb44))


## v0.11.5 (2026-09-21)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`9e44edf`](https://github.com/pelukron/hermes-scripts/commit/9e44edf0c4c4f8341410fbb9551eaba1a6941352))


## v0.11.4 (2026-09-21)

### 🐛 Fixes

- El test de bump-and-pr ya no depende de la rama del checkout
  ([`e4b95b5`](https://github.com/pelukron/hermes-scripts/commit/e4b95b554538f1cb22ca6dfc070e975511e062a7))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e30e21c`](https://github.com/pelukron/hermes-scripts/commit/e30e21cbb42b81e353388ce60fcd9ca3050eedf6))


## v0.11.3 (2026-09-20)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`de07e03`](https://github.com/pelukron/hermes-scripts/commit/de07e033539d83d4bd287971c4f1e53c60227193))


## v0.11.2 (2026-09-19)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`3fd6df1`](https://github.com/pelukron/hermes-scripts/commit/3fd6df162f940f2fb34c7b8aca1f2aa5b9c5cf82))


## v0.11.1 (2026-09-19)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`5558286`](https://github.com/pelukron/hermes-scripts/commit/5558286d79409a52b9365618a388e20b08d49d29))


## v0.11.0 (2026-09-19)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`f0eea1f`](https://github.com/pelukron/hermes-scripts/commit/f0eea1f324e7f31d9ff1d1f8fcf3187a01545e6f))


## v0.10.2 (2026-09-19)

### 🐛 Fixes

- Reloj inyectable en monitor-ram
  ([`613088f`](https://github.com/pelukron/hermes-scripts/commit/613088fbf9ff2fb3689d289f7f082423624644a0))

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`485a853`](https://github.com/pelukron/hermes-scripts/commit/485a853ca9468b466a42d6372300b9d48edd1735))


## v0.10.1 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`ba56fb6`](https://github.com/pelukron/hermes-scripts/commit/ba56fb66171f64e48797c75f35b0817c1189b586))


## v0.10.0 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e07b3a6`](https://github.com/pelukron/hermes-scripts/commit/e07b3a6d48bca0824a7ba6ddf4ec8f67c613fed1))

### ✨ Features

- Doctor diario con expectativas por job (cron-doctor-daily, modo --expectations)
  ([#217](https://github.com/pelukron/hermes-scripts/pull/217),
  [`f1c65f0`](https://github.com/pelukron/hermes-scripts/commit/f1c65f03029bdc4851966027b76e4f450385f6c9))


## v0.9.4 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`9ab9cdb`](https://github.com/pelukron/hermes-scripts/commit/9ab9cdb3fe6837018a48cac2d05c6477f1837747))


## v0.9.3 (2026-09-18)

### 📦 Chores

- Seam de directorio de estado ($HERMES_HOME) para que los entrypoints sean sandboxeables
  ([#215](https://github.com/pelukron/hermes-scripts/issues/215),
  [#215](https://github.com/pelukron/hermes-scripts/pull/215),
  [`01a58a0`](https://github.com/pelukron/hermes-scripts/commit/01a58a02738f0675f8727e3175c1ce9842942246))

- Sync uv.lock tras release [skip ci]
  ([`08175ac`](https://github.com/pelukron/hermes-scripts/commit/08175ace6bd9646dcf3e107a5694e8731fe98aad))


## v0.9.2 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`d897d4c`](https://github.com/pelukron/hermes-scripts/commit/d897d4cb0194ecc0dad62b809f3f443ab358792a))


## v0.9.1 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`bbf20ab`](https://github.com/pelukron/hermes-scripts/commit/bbf20ab0dbd0929f34a02d370c58c9cb756ddf89))


## v0.9.0 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`efe421f`](https://github.com/pelukron/hermes-scripts/commit/efe421f427d5bcfdd22fd21d22cad9ca7f9b3769))


## v0.8.3 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`358d98a`](https://github.com/pelukron/hermes-scripts/commit/358d98ab90c1faa268b8a089824913ae2bb7fd8d))


## v0.8.2 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e44739d`](https://github.com/pelukron/hermes-scripts/commit/e44739d536c7487d01c8ebfd5010785a74119583))


## v0.8.1 (2026-09-18)


## v0.8.0 (2026-09-18)


## v0.7.1 (2026-09-18)


## v0.7.0 (2026-09-18)


## v0.6.1 (2026-09-18)


## v0.6.0 (2026-09-18)

### 🔧 Infra

- Asignar issues a @pelukron (regla + script)
  ([`53377df`](https://github.com/pelukron/hermes-scripts/commit/53377df38532488e4c39a05e6e280d606dfae802))

- El push del release salia como github-actions[bot]
  ([##204](https://github.com/pelukron/hermes-scripts/pull/204),
  [`906bac7`](https://github.com/pelukron/hermes-scripts/commit/906bac7f553aa48da4d8d3f4274118693041ee0e))

- Ignorar artefactos de coverage
  ([`7ced0f9`](https://github.com/pelukron/hermes-scripts/commit/7ced0f9ab9e71c795e97cabf24bc0c74d69fb469))

- Los avisos de infra declaran el target notify (canal de repos)
  ([`b325d7b`](https://github.com/pelukron/hermes-scripts/commit/b325d7b951992d4ceb0181dd70fca8c274d42ba5))

- Mover el backup diario a las 04:10, fuera de la ventana peak
  ([`5f37ac8`](https://github.com/pelukron/hermes-scripts/commit/5f37ac83a5c001c4855de31b9c28bc99876600f8))

- Release en cada merge + seccion Releases en README
  ([`f6d2b41`](https://github.com/pelukron/hermes-scripts/commit/f6d2b4149cd08acdbcd05f167488d942ebeda89e))


### 🤖 Automation
- PRs piden review a `@pelukron` (workflow `pr-review` + `bump-and-pr.sh`); regla en `AGENTS.md`
  [#108](https://github.com/pelukron/hermes-scripts/issues/108)

## [0.5.4] - 2026-09-15

### 📝 Documentation
- `CONTEXT.md`: vocabulario compartido, gate y CI, nomenclatura, mapa del repo, auditoría cross-repo 2026-09-15 y orden de ejecución
  [#98](https://github.com/pelukron/hermes-scripts/issues/98)

## [0.5.3] - 2026-09-15

### 🤖 Automation
- `gate-audit`: matriz de gates por repo (`src/gate_audit.py` + `bin/gate-audit.py --markdown/--digest` → `out/gate-audit.md`) + 4 tests sin red
  [#99](https://github.com/pelukron/hermes-scripts/issues/99)

## [0.5.2] - 2026-09-15

### 📝 Documentation
- `AGENTS.md`: reglas del agente (work order, gate, CHANGELOG, ramas, no force, no merge) + enlaces a proceso y contexto
  [#101](https://github.com/pelukron/hermes-scripts/issues/101)

## [0.5.1] - 2026-09-15

### 🔧 Changed
- `bin/gate.sh`: entrypoint único del quality-gate (`exec make check`); `ci.yml` lo llama sin duplicar pasos; README documenta el gate
  [#100](https://github.com/pelukron/hermes-scripts/issues/100)

## [0.5.0] - 2026-09-15

### ✨ Added(cron)
- cron/jobs.json: manifiesto declarativo, fuente de verdad de los 12 jobs (schedule, wrapper, deliver, enabled, requires)
- bin/install-cron.sh + src/install_cron.py: wrappers portables, upsert idempotente con hermes cron, modos --dry-run / --check / --force y verificacion read-back
- tests/test_install_cron.py: 37 tests (valida el manifiesto real, prohibe rutas /home/<usuario> en archivos versionados, bash -n de bin/*.sh, plan create/edit/pause sin efectos)
- docs/INSTALL.md + env.example + cron/targets.example.json: instalacion reproducible sin IDs de chat versionados
- bin/aviso-peak.sh: aviso 5 min antes de cada ventana peak de la API DeepSeek (18:55 y 23:55, hora Monterrey)
- fix: resumen-rayados/tigres usaban una ruta absoluta de uv de otro equipo
  [#96](https://github.com/pelukron/hermes-scripts/issues/96)
## [Unreleased]

## [0.4.0] - 2026-09-10

### 🚀 Added
- `hermes_common`: filtrar pubs >48h (`parse_published`, `is_within_max_age`, `filter_by_max_age`); Tigres/Rayados antes del historial (#89)
- `retry_request`: body cap 2MB + streaming (#68)
- Script `cleanup-housekeeping.py`: backups viejos (keep 3), noticias >4d, caches npm/pnpm/pip
  [#82](https://github.com/pelukron/hermes-scripts/pull/82)
- Script `resumen-tigres-diario.py`: noticias Tigres UANL (Google News RSS + tigres.com.mx), confirmadas vs rumores, dedupe 72h, cron 9AM → canal Tigres

### 🐛 Fixed
- SQL f-string → parametros SQLite en `reporte-uso-hermes.py`
- Validar `days` entero positivo [#61](https://github.com/pelukron/hermes-scripts/issues/61)

### 📝 Documentation
- `PROJECT_MANAGEMENT.md` Jira-style: epics, milestones, board
- Milestones v0.4.0−v0.6.0 + board [#58](https://github.com/pelukron/hermes-scripts/issues/58)

### 🔧 Changed
- Scripts PM react-stack-roadmap adaptados: gh-issue, gh-pr, pm-status, pm-weekly
- workflow `project-automation.yml`: auto-add épicas al board #3
- Épicas #58/#59/#60: emojis + secciones estandarizadas
- Regla de emojis en Issues → PROJECT_MANAGEMENT.md [#76](https://github.com/pelukron/hermes-scripts/issues/76)
- `backup-diario.py`: rutas absolutas, tamaño artefactos, cuerpo [Unreleased]
- `retry_request` reusa `requests.Session` (#66)

### 🛡️ Security
- `xml.etree.ElementTree` → `defusedxml` parseo RSS; resuelve bandit B405/B314 [#62](https://github.com/pelukron/hermes-scripts/issues/62)

### 🔊 Observability
- `except Exception: pass` → `logging.warning` (noticias, rayados, common); resuelve bandit B110 [#63](https://github.com/pelukron/hermes-scripts/issues/63)

### 🤖 CI
- Mypy+bandit a todo repo (no solo src/): Makefile+CI; excluir tests/; 6 annotations corregidas [#64](https://github.com/pelukron/hermes-scripts/issues/64)

### 🛡️ Security
- Validar subprocess paths (polymarket, uv, git); capturar stderr [#65](https://github.com/pelukron/hermes-scripts/issues/65)

## [0.3.22] - 2026-07-14

### 🤖 CI
- Extender condición del changelog check para ignorar PRs desde ramas automáticas
- Mantener exclusión por actor: dependabot[bot] y github-actions[bot]
- Agregar exclusión por prefijo de rama: dependabot/* y github-actions/*
- Evitar fallos falsos en PRs automáticos de Dependabot
  [#56](https://github.com/pelukron/hermes-scripts/issues/56)

## [0.3.21] - 2026-07-14

### 🐛 Fixed
- Corregir `bump-and-pr.sh` para insertar entradas de CHANGELOG en orden descendente
- Corregir posición de comparison URLs al inicio de la sección de referencias
- Mover `Closes #N` al inicio del PR body para cierre automático de issues
- Usar `$GITHUB_TOKEN` real en lugar de placeholder en llamadas curl
  [#51](https://github.com/pelukron/hermes-scripts/issues/51)

## [0.3.20] - 2026-07-14

### 🤖 CI
- Excluir a `dependabot[bot]` y `github-actions[bot]` del changelog check
- Evitar fallos falsos en PRs automáticos de dependencias
  [#51](https://github.com/pelukron/hermes-scripts/issues/51)

## [0.3.19] - 2026-07-14

### 🤖 CI
- Agregar Dependabot para actualizaciones de dependencias y GitHub Actions
- Agregar CodeQL workflow para análisis de seguridad estático en Python
  [#46](https://github.com/pelukron/hermes-scripts/issues/46)

## [0.3.18] - 2026-07-14

### 📝 Documentation
- Reparar header corrupto y líneas sueltas en CHANGELOG.md
- Ordenar comparison URLs en orden descendente
  [#44](https://github.com/pelukron/hermes-scripts/issues/44)

### 🔧 Changed
- Agregar `.mypy_cache/` a `.gitignore` para evitar caché de mypy en commits
  [#44](https://github.com/pelukron/hermes-scripts/issues/44)

## [0.3.17] - 2026-07-13

### 📝 Documentation
- Corregir referencias faltantes a `bin/` y `src/` en README, CONTRIBUTING y HERMES_DEV_FLOW
  [#42](https://github.com/pelukron/hermes-scripts/issues/42)

## [0.3.16] - 2026-07-13

### 🔧 Changed
- Mover scripts shell a `bin/`
- Mover `generate-issue-body.py` a `src/`
- Corregir ruta interna en `bump-and-pr.sh`
- Actualizar README, CONTRIBUTING y setup.sh con nuevas rutas
  [#40](https://github.com/pelukron/hermes-scripts/issues/40)

## [0.3.15] - 2026-07-11

### 📝 Documentation
- Eliminar líneas 'documentados aquí...' repetidas entre versiones
- Eliminar texto 'Todos los cambios notables' suelto
- Unificar [0.3.2] duplicado en una sola entrada
- Eliminar link de referencia [0.3.2] duplicado
- Links de comparación ordenados y sin duplicados
  [#37](https://github.com/pelukron/hermes-scripts/issues/37)


## [0.3.14] - 2026-07-11

### 📝 Documentation
- Agregar emojis en headers de CHANGELOG: 🐛 ✨ 🔧 📝 🤖 🧪 📦
- Mismos emojis que labels de issues y PRs
- Actualizar CATEGORY en bump-and-pr.sh para generar emojis automáticos
  [#35](https://github.com/pelukron/hermes-scripts/issues/35)


## [0.3.13] - 2026-07-11

### 🤖 CI
- Agregar mypy type checking en CI
- Agregar Bandit security scan en CI
- Configurar [tool.mypy] y [tool.bandit] en pyproject.toml
  [#33](https://github.com/pelukron/hermes-scripts/issues/33)


## [0.3.12] - 2026-07-11

### 📝 Documentation
- Agregar sección 'Proceso Manual' con 12 pasos detallados
- Tabla de tipos de cambio con labels y emojis
- Actualizar pipeline automatizado con nuevas features (emojis, labels)
- Corregir sección CI (149 tests → Tests)
  [#31](https://github.com/pelukron/hermes-scripts/issues/31)


## [0.3.11] - 2026-07-11

### 🐛 Fixed
- Reutilizar cuerpo enriquecido del issue en el PR body
- Agregar emojis en headers: 🔗 📦 📝 ⚡
- Eliminar PR body minimal hardcodeado
  [#29](https://github.com/pelukron/hermes-scripts/issues/29)


## [0.3.10] - 2026-07-11

### 🔧 Changed
- Mover hermes_common.py a src/hermes_common/ como paquete con __init__.py
- Mover feeds.json a config/
- Actualizar pyproject.toml: packages=['src']
- Agregar .hermes/ a .gitignore
- Actualizar tests para nuevo path de modulo
  [#27](https://github.com/pelukron/hermes-scripts/issues/27)


## [0.3.9] - 2026-07-11

### 🐛 Fixed
- CHANGELOG: reemplazado [#N](url) literal por link real [#23](https://github.com/pelukron/hermes-scripts/issues/23)

## [0.3.8] - 2026-07-11

### 🔧 Changed
- Release notes incluyen link al issue [#23](https://github.com/pelukron/hermes-scripts/issues/23)
- CHANGELOG incluye link al issue automáticamente

## [0.3.7] - 2026-07-11

### 🐛 Fixed
- Auto-release: busca issue en PR body cuando es squash merge

## [0.3.6] - 2026-07-11

### 🐛 Fixed
- Auto-release: permisos contents:write para que el bot pueda pushear tags

## [0.3.5] - 2026-07-11

### ✨ Added
- Auto-release: tag + release + issue comment automático al mergear a main

## [0.3.4] - 2026-07-11

### ✨ Added
- CI: changelog check bloquea PRs sin actualizar CHANGELOG.md

## [0.3.3] - 2026-07-11

### 🐛 Fixed
- pre-push hook: permite tags, solo bloquea refs/heads/main


## [0.3.2] - 2026-07-11

### ✨ Added
- Script setup.sh: configura git hooks, uv sync, pre-commit, verifica GITHUB_TOKEN

### 📝 Documentation
- Verificar flujo completo: Issue automático + PR vinculado + Closes #N

## [0.3.1] - 2026-07-11

### 🐛 Fixed
- Eliminados `import random` muertos en 3 scripts (monitor-ram, noticias, rayados)
- Eliminado `import time` muerto en `polymarket-diario.py`
- Eliminado `typing.Optional` no usado en `hermes_common.py`
- Eliminado `return None` inalcanzable en `retry_request()`
- Simplificada cláusula `except`: removidos `ConnectionError`/`TimeoutError` redundantes
- Renombrado test `test_return_none_cuando_falla_silencioso` → `test_propaga_excepcion_no_retryable`

## [0.3.0] - 2026-07-11

### ✨ Added
- `retry_request()` unificada en `hermes_common.py` (exponential backoff + jitter)
- `test_hermes_common.py` con 9 tests dedicados a `retry_request()`
- Adaptadores de skills mattpocock: `grill`, `grill-docs`, `code-review`, `diagnosing-bugs`, `handoff`
- `update-external-skills.sh` para sincronizar repos externos

### 🔧 Changed
- `retry_request()` centralizada: eliminadas 5 copias duplicadas en 5 scripts
- Tests migrados de `patch.object(mod, "retry_request")` a `patch("requests.get")` directo
- `hermes_common.py` ahora expone `retry_request()` junto a `get_headers()`, `smart_truncate()`, `HistoryManager`
- 149 tests (reducido de 167 por eliminación de tests duplicados, más robustos)

### 🐛 Fixed
- `resumen-rayados-diario.py` usa `retry_request()` desde `hermes_common` en vez de copia local
- `polymarket-diario.py` usa `retry_request()` desde `hermes_common` con headers API

### ✨ Added
- `retry_request()` en `polymarket-diario.py` y `monitor-ram-mexico.py` para llamadas HTTP
- Docstrings Google-style en todos los scripts
- Tests pytest: 128 tests (resumen-noticias, rayados, reporte-uso, backup, polymarket, monitor-ram)
- Skills importadas de awesome-copilot: `conventional-commit`, `git-commit`, `github-release`
- CHANGELOG.md en formato Keep a Changelog

### 🔧 Changed
- ruff format + ruff check en 5 scripts (0 warnings)
- `resumen-rayados-diario.py` reformateado (556→560 líneas)
- `polymarket-diario.py` migrado de `urllib` a `requests` con `retry_request()`

## [0.1.0] - 2026-07-10

### ✨ Added
- Script `resumen-noticias-diario.py` con 12 secciones y 39 fuentes RSS multi-ideología
- Sección `🔍 INVESTIGACIÓN & ANÁLISIS` vía blogwatcher (The Intercept, Stratechery)
- Sección `🤖 IA & TECH` con TechCrunch, MIT AI y Wired
- `retry_request()` con exponential backoff + jitter para 39 endpoints HTTP
- `FeedStats` dataclass con tracking de fuentes fallidas
- `feeds.json` externo para configuración editable sin tocar código Python
- Footer stats: `📊 36/39 OK (3 fallos: X, Y, Z)`
- 29 tests pytest para funciones clave
- Skills `python-error-handling` y `python-resilience` de wshobson/agents
- Git + commitizen para versionado semántico con conventional commits
- Skill `conventional-commits` con flujo de trabajo documentado
- Skill `keep-a-changelog` con formato estándar

### 🔧 Changed
- `fetch_rss()`, `fetch_crypto()`, `fetch_currencies()` usan `retry_request()` con backoff
- Formato de salida atomizado con `time.sleep()` entre secciones
- URLs de Google News acortadas vía TinyURL
- Configuración de feeds extraída a `feeds.json`

### 🐛 Fixed
- Tracking de fuentes fallidas ahora reporta nombres reales en footer
- URLs con `)` escapadas a `%29` para evitar rotura de links Markdown
- Títulos con `[]` limpiados para evitar conflicto con sintaxis de links

[0.5.5]: https://github.com/pelukron/hermes-scripts/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/pelukron/hermes-scripts/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/pelukron/hermes-scripts/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/pelukron/hermes-scripts/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/pelukron/hermes-scripts/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/pelukron/hermes-scripts/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/pelukron/hermes-scripts/compare/v0.3.22...v0.4.0
[0.3.22]: https://github.com/pelukron/hermes-scripts/compare/v0.3.21...v0.3.22
[0.3.21]: https://github.com/pelukron/hermes-scripts/compare/v0.3.20...v0.3.21
[0.3.20]: https://github.com/pelukron/hermes-scripts/compare/v0.3.19...v0.3.20
[0.3.19]: https://github.com/pelukron/hermes-scripts/compare/v0.3.18...v0.3.19
[0.3.18]: https://github.com/pelukron/hermes-scripts/compare/v0.3.17...v0.3.18
[0.3.17]: https://github.com/pelukron/hermes-scripts/compare/v0.3.16...v0.3.17
[0.3.16]: https://github.com/pelukron/hermes-scripts/compare/v0.3.15...v0.3.16
[0.3.15]: https://github.com/pelukron/hermes-scripts/compare/v0.3.14...v0.3.15
[0.3.14]: https://github.com/pelukron/hermes-scripts/compare/v0.3.13...v0.3.14
[0.3.13]: https://github.com/pelukron/hermes-scripts/compare/v0.3.12...v0.3.13
[0.3.12]: https://github.com/pelukron/hermes-scripts/compare/v0.3.11...v0.3.12
[0.3.11]: https://github.com/pelukron/hermes-scripts/compare/v0.3.10...v0.3.11
[0.3.10]: https://github.com/pelukron/hermes-scripts/compare/v0.3.9...v0.3.10
[0.3.9]: https://github.com/pelukron/hermes-scripts/compare/v0.3.8...v0.3.9
[0.3.8]: https://github.com/pelukron/hermes-scripts/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/pelukron/hermes-scripts/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/pelukron/hermes-scripts/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/pelukron/hermes-scripts/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/pelukron/hermes-scripts/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/pelukron/hermes-scripts/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/pelukron/hermes-scripts/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/pelukron/hermes-scripts/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/pelukron/hermes-scripts/compare/v0.1.0...v0.3.0
