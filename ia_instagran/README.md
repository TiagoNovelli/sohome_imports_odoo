Configurar nossos concorrentes e clientes no instagram para armazenar os arquivos

https://github.com/instaloader/instaloader

Treinar Yolo para nossa regra de negócio

# Furniture Vision AI — Catálogo Inteligente Sohome

Este projeto tem como objetivo criar uma estrutura de visão computacional especializada em móveis de alto padrão utilizando YOLOv8, segmentação e fine tuning de modelos pré-treinados de furniture detection.

O sistema será capaz de:

* detectar móveis em ambientes
* identificar módulos/configurações de sofás
* reconhecer componentes visuais
* identificar tecidos e cores
* realizar busca visual no catálogo
* integrar os resultados ao Odoo
* auxiliar representantes comerciais
* alimentar orçamentos automaticamente

O projeto utiliza como ponto de partida o modelo:

```text
MaherMohsen/furniture-yolov8
```

Disponível em:

[https://huggingface.co/MaherMohsen/furniture-yolov8](https://huggingface.co/MaherMohsen/furniture-yolov8)

Esse modelo já possui conhecimento especializado em:

* furniture detection
* furniture segmentation
* ambientes internos
* sofás
* cadeiras
* mesas
* composição de salas
* interior design
* e-commerce de mobiliário

A estratégia é utilizar esse modelo como base e realizar fine tuning com o catálogo próprio da Sohome.

A estratégia recomendada é dividir o problema em etapas, porque o catálogo possui muitas configurações: sofá com braço, sem braço, com curva, com almofada, sem almofada, chaise, módulos, tecidos e cores.

Em vez de treinar uma única classe para cada combinação possível, o ideal é separar o reconhecimento em partes:

1. **Detecção do produto principal**
   Identificar o item base na imagem: sofá, poltrona, mesa, puff, módulo, chaise etc.

2. **Detecção dos componentes/configurações**
   Identificar características visuais do produto: braço esquerdo, braço direito, módulo sem braço, módulo curvo, almofada solta, encosto, chaise, canto, terminal etc.

3. **Classificação de tecido/cor**
   Depois que o produto ou região for localizado, recortar a área relevante e classificar o tecido/cor: linho bege, veludo cinza, couro caramelo, boucle off white etc.

Essa separação evita criar muitas classes combinadas, como `sofa_com_braco_linho_bege`, `sofa_sem_braco_veludo_cinza`, `modulo_curvo_boucle_offwhite`, etc.

Em vez disso, o sistema trabalha assim:

```text
imagem da sala
   ↓
YOLO detecta o produto principal
   ↓
YOLO ou segmentação detecta componentes/configurações
   ↓
recorta regiões relevantes
   ↓
modelo classificador identifica tecido/cor
   ↓
sistema combina os resultados
```

Exemplo de saída esperada:

```json
{
  "produto_base": "sofa_modular",
  "componentes": [
    "braco_esquerdo",
    "modulo_sem_braco",
    "modulo_curvo",
    "almofada_soltas"
  ],
  "tecido": "linho_bege"
}
```

---

## 1. Arquitetura Geral

```text
Furniture YOLO pré-treinado
        ↓
Fine tuning com catálogo Sohome
        ↓
Detecção de módulos/componentes
        ↓
Classificação de tecido/cor
        ↓
Integração com Odoo
```

---

## 2. Por que usar um modelo furniture pré-treinado?

Treinar um modelo do zero exigiria milhares de imagens.

O modelo `MaherMohsen/furniture-yolov8` já entende:

* geometria de móveis
* ambientes internos
* composição de salas
* proporções de mobiliário
* oclusões
* segmentação de objetos
* cenários de decoração

Isso reduz bastante a quantidade de imagens necessárias para o fine tuning.

Em vez de ensinar o modelo a entender o conceito de sofá do zero, o projeto apenas especializa o conhecimento para o catálogo Sohome.

---

## 3. Instalação das dependências

Instale as bibliotecas necessárias:

```bash
pip install ultralytics opencv-python
```

Teste a instalação:

```bash
yolo version
```

Ou em Python:

```python
from ultralytics import YOLO

model = YOLO("furniture-yolov8.pt")
print(model)
```

---

## 4. Modelo inicial de detecção

Exemplo básico usando um modelo pré-treinado YOLOv8:

```python
from ultralytics import YOLO
import cv2

# Carrega modelo pré-treinado
model = YOLO("yolov8n.pt")

# Caminho da imagem
img_path = r"C:\Users\tiago.premiano\Downloads\sala3.jpeg"

# Detecta objetos
results = model(img_path)

# Desenha caixas na imagem
annotated = results[0].plot()

# Mostra resultado
cv2.imshow("Detecção", annotated)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

Esse modelo identifica objetos genéricos, como pessoa, cadeira, sofá, mesa etc. Para reconhecer os produtos específicos do catálogo, é necessário treinar com imagens próprias.

---

## 5. Fine Tuning do Modelo Furniture

### 3.1 Estrutura do dataset

Crie uma pasta para o dataset de detecção:

```text
dataset_sohome/
  images/
    train/
    val/
  labels/
    train/
    val/
  data.yaml
```

Onde:

* `images/train/`: imagens usadas para treinamento
* `images/val/`: imagens usadas para validação
* `labels/train/`: anotações das imagens de treino
* `labels/val/`: anotações das imagens de validação
* `data.yaml`: arquivo de configuração das classes

---

### 3.2 Exemplo do arquivo `data.yaml`

```yaml
path: C:/Users/tiago.premiano/dataset_sohome
train: images/train
val: images/val

names:
  0: sofa_confort
  1: poltrona_confort
  2: sofa_modular
  3: mesa_lateral
  4: cadeira
  5: puff
```

Cada classe representa um tipo de produto que o modelo deve aprender a detectar.

---

### 3.3 Formato das anotações YOLO

Para cada imagem, deve existir um arquivo `.txt` com o mesmo nome.

Exemplo:

```text
images/train/sala001.jpg
labels/train/sala001.txt
```

Conteúdo do arquivo `.txt`:

```text
0 0.512 0.430 0.700 0.380
```

Formato:

```text
classe x_centro y_centro largura altura
```

Todos os valores de posição e tamanho são normalizados entre `0` e `1`.

Exemplo:

```text
0 = sofa_confort
0.512 = centro da caixa no eixo X
0.430 = centro da caixa no eixo Y
0.700 = largura da caixa
0.380 = altura da caixa
```

---

## 4. Ferramentas para anotar imagens

Para criar as caixas dos produtos nas imagens, utilize uma ferramenta de anotação:

* CVAT
* Roboflow
* Label Studio
* LabelImg

O processo é:

1. Enviar as imagens para a ferramenta
2. Desenhar uma caixa em volta de cada produto
3. Escolher a classe correta
4. Exportar no formato YOLO
5. Colocar os arquivos nas pastas `images/` e `labels/`

---

## 5. Treinamento do modelo de detecção

Arquivo exemplo: `train_detect.py`

```python
from ultralytics import YOLO

# Carrega modelo furniture pré-treinado
model = YOLO("furniture-yolov8.pt")

# Treina com o dataset próprio
results = model.train(
    data="C:/Users/tiago.premiano/dataset_sohome/data.yaml",
    epochs=100,
    imgsz=640,
    batch=8
)
```

Após o treinamento, o melhor modelo será salvo em um caminho parecido com:

```text
runs/detect/train/weights/best.pt
```

---

## 6. Inferência e testes

Arquivo exemplo: `predict_detect.py`

```python
from ultralytics import YOLO
import cv2

# Carrega o modelo treinado
model = YOLO("runs/detect/train/weights/best.pt")

# Imagem para teste
img_path = r"C:\Users\tiago.premiano\Downloads\sala3.jpeg"

# Faz a detecção
results = model(img_path)

# Desenha as caixas
annotated = results[0].plot()

# Mostra a imagem
cv2.imshow("Detecção Sohome", annotated)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

---

## 7. Detecção de módulos e componentes

O diferencial do projeto é que ele não detecta apenas “sofás”.

O objetivo é detectar componentes/configurações dos produtos.

Exemplo:

```json
{
  "produto_base": "sofa_modular",
  "componentes": [
    "braco_esquerdo",
    "modulo_curvo",
    "chaise_direita"
  ]
}
```

Isso permite reconhecer diferentes composições do catálogo.

Exemplos de componentes:

```text
braco_esquerdo
braco_direito
modulo_reto
modulo_curvo
chaise
terminal
sem_braco
almofada_solta
almofada_fixa
encosto
```

---

## 8. Classificação de tecido e cor

A ideia é:

1. O modelo de detecção encontra o produto
2. O produto é recortado da imagem
3. O recorte é enviado para um classificador
4. O classificador retorna o tecido/cor provável

---

### 7.1 Estrutura do dataset de tecidos

```text
dataset_tecidos/
  train/
    linho_bege/
    veludo_cinza/
    couro_caramelo/
    boucle_offwhite/
  val/
    linho_bege/
    veludo_cinza/
    couro_caramelo/
    boucle_offwhite/
```

Cada pasta representa uma classe.

Exemplo:

```text
dataset_tecidos/train/linho_bege/img001.jpg
dataset_tecidos/train/linho_bege/img002.jpg
dataset_tecidos/train/veludo_cinza/img001.jpg
```

---

### 7.2 Treinamento do classificador

Arquivo exemplo: `train_tecidos.py`

```python
from ultralytics import YOLO

# Modelo base para classificação
model = YOLO("yolov8n-cls.pt")

# Treina classificador de tecidos/cores
model.train(
    data="C:/Users/tiago.premiano/dataset_tecidos",
    epochs=80,
    imgsz=224
)
```

Após o treinamento, o modelo será salvo em um caminho parecido com:

```text
runs/classify/train/weights/best.pt
```

---

## 9. Quantidade recomendada de imagens

Para começar com boa qualidade:

### Detecção de produtos

* 100 a 300 imagens por tipo de produto
* Fotos em diferentes ambientes
* Fotos com diferentes ângulos
* Fotos com iluminação variada
* Produtos parcialmente escondidos, quando possível

### Classificação de tecidos/cores

* 50 a 150 imagens por tecido/cor
* Fotos próximas do tecido
* Fotos em ambientes reais
* Fotos com variação de luz
* Imagens do catálogo e imagens reais de clientes/ambientes

Quanto maior a variação das imagens, melhor o modelo tende a generalizar.

---

## 10. Exemplo de classes recomendadas

### Modelo de detecção do produto principal

```text
sofa
poltrona
mesa_lateral
mesa_centro
cadeira
puff
sofa_modular
chaise
```

### Modelo de detecção de componentes/configurações

```text
braco_esquerdo
braco_direito
sem_braco
modulo_reto
modulo_curvo
chaise_esquerda
chaise_direita
canto
terminal
almofada_soltas
almofada_fixa
encosto
base
```

Também é possível usar uma única detecção mais detalhada, por exemplo:

```text
sofa_com_braco
sofa_sem_braco
sofa_com_curva
sofa_com_chaise
modulo_reto_sem_braco
modulo_curvo
```

Mas, quanto mais detalhada for a classe, mais imagens serão necessárias para cada variação.

### Modelo de tecido/cor

```text
linho_bege
linho_areia
veludo_cinza
veludo_azul
couro_caramelo
couro_preto
boucle_offwhite
suede_marrom
```

---

## 11. Por que não criar uma classe para cada combinação?

Evite criar classes como:

```text
sofa_com_braco_linho_bege
sofa_com_braco_veludo_cinza
sofa_sem_braco_linho_bege
sofa_curvo_boucle_offwhite
sofa_com_chaise_couro_caramelo
```

Isso aumenta muito o número de classes e exige muitas imagens para cada combinação.

Melhor separar:

```text
produto_base = sofa_modular
componentes = braco_esquerdo + modulo_curvo + chaise_direita
tecido = linho_bege
```

Assim, o sistema fica mais flexível e escalável.

### Exemplo prático

Em vez de tentar ensinar ao modelo uma classe única chamada:

```text
sofa_modular_com_braco_esquerdo_modulo_curvo_chaise_direita_linho_bege
```

O sistema pode aprender partes separadas:

```text
produto_base: sofa_modular
componente_1: braco_esquerdo
componente_2: modulo_curvo
componente_3: chaise_direita
tecido: linho_bege
```

Depois, uma regra de negócio combina esses resultados e consulta o catálogo/Odoo para encontrar o produto correspondente.

---

## 12. Segmentação: quando usar

A detecção comum usa caixas retangulares em volta dos objetos.

Exemplo:

```text
[ caixa em volta do sofá ]
```

Se for necessário identificar o contorno exato do produto, use segmentação.

Segmentação é útil para:

* recortar o sofá com mais precisão
* trocar tecido digitalmente
* remover fundo
* calcular área visual do produto
* criar aplicações de decoração e composição de ambiente

Nesse caso, em vez de um modelo `detect`, seria usado um modelo `segment`, como:

```python
from ultralytics import YOLO

model = YOLO("yolov8n-seg.pt")

model.train(
    data="C:/Users/tiago.premiano/dataset_segmentacao/data.yaml",
    epochs=100,
    imgsz=640
)
```

---

## 13. Estrutura sugerida do projeto

```text
visao_catalogo_sohome/
  README.md
  requirements.txt

  datasets/
    dataset_sohome/
      images/
        train/
        val/
      labels/
        train/
        val/
      data.yaml

    dataset_tecidos/
      train/
      val/

  scripts/
    train_detect.py
    predict_detect.py
    train_tecidos.py
    predict_tecidos.py
    crop_detections.py

  models/
    detection/
      best.pt
    tecidos/
      best.pt

  outputs/
    detections/
    crops/
    predictions/
```

---

## 14. Arquivo `requirements.txt`

```text
ultralytics
opencv-python
```

Instalação:

```bash
pip install -r requirements.txt
```

---

## 15. Próximos passos recomendados

1. Definir quais produtos serão detectados
2. Criar uma lista inicial de classes
3. Separar imagens reais do catálogo e de ambientes
4. Anotar as imagens com caixas no formato YOLO
5. Treinar o primeiro modelo de detecção
6. Testar com fotos reais
7. Criar dataset separado para tecidos/cores
8. Treinar classificador de tecido/cor
9. Integrar os resultados com o catálogo ou ERP/Odoo

---

## 16. Possível integração futura com Odoo

Depois que os modelos estiverem funcionando, o resultado pode ser integrado ao Odoo.

Exemplo de saída esperada:

```json
{
  "produto_detectado": "sofa_confort",
  "confianca_produto": 0.91,
  "tecido_detectado": "linho_bege",
  "confianca_tecido": 0.87
}
```

Com isso, seria possível:

* sugerir produtos semelhantes do catálogo
* identificar produtos em fotos de ambientes
* ajudar representantes comerciais
* cruzar imagem com mix disponível por cliente
* alimentar propostas/orçamentos no Odoo
* criar busca visual de produtos

---

## 17. Observação importante

O modelo só aprende bem aquilo que aparece bem representado no dataset.

Se o catálogo tiver muitas variações de produto, tecido, cor, iluminação e ângulo, o dataset precisa refletir essa variedade.

A qualidade do modelo depende principalmente de:

* qualidade das imagens
* quantidade de exemplos
* qualidade das anotações
* classes bem definidas
* validação com imagens reais
