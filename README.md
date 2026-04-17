# 🚀 Flask API Service – Guia de Execução

Este projeto é uma API simples desenvolvida com **Flask**, baseada no guia oficial do Google Cloud Run.

O objetivo deste guia é ajudar você a executar o projeto localmente de forma rápida e sem complicações.

---

## 📋 Pré-requisitos

Antes de começar, verifique se você possui instalado:

* **Python 3.10**
* **pip (gerenciador de pacotes do Python)**

### ⚠️ Dependência opcional (importante para câmeras RTSP)

Se o projeto utilizar câmeras (RTSP), será necessário instalar o **FFmpeg**:

#### Windows:

```bash
winget install Gyan.FFmpeg
```

#### Linux (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install ffmpeg -y
```

---

## ▶️ Como executar o projeto

### 🔹 Opção 1 — Execução automática (recomendado)

Se o ambiente já estiver configurado corretamente, basta rodar:

```bash
./devserver.sh
```

Esse script irá automaticamente:

* Atualizar o pip
* Instalar as dependências
* Iniciar o servidor Flask

---

### 🔹 Opção 2 — Execução manual

Caso prefira executar passo a passo:

#### 1. Criar ambiente virtual

```bash
python3 -m venv .venv310
```

#### 2. Ativar o ambiente virtual

* Linux/Mac:

```bash
source .venv310/bin/activate
```

* Windows:

```bash
.\.venv310\Scripts\activate
```

#### 3. Instalar dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Iniciar o servidor

```bash
python -u -m flask --app main run --debug
```

---

## 🌐 Acessando a API

Após iniciar o servidor, a API estará disponível em:

```
http://127.0.0.1:5000
```

---

## 🛠️ Estrutura básica

* `main.py` → Arquivo principal da aplicação Flask
* `requirements.txt` → Lista de dependências
* `devserver.sh` → Script automatizado de execução

---

## ❗ Problemas comuns

### 🔸 "python não encontrado"

Verifique se o Python está instalado corretamente e adicionado ao PATH.

### 🔸 Erro ao instalar dependências

Tente atualizar o pip:

```bash
pip install --upgrade pip
```

### 🔸 Problemas com câmera (RTSP)

Certifique-se de que o **FFmpeg** está instalado corretamente.

---

## 💡 Observação

O projeto roda em modo **debug**, ideal para desenvolvimento.
Não é recomendado usar essa configuração em produção.

---

Se tiver dúvidas durante a execução, siga os passos com atenção ou peça ajuda ao responsável pelo projeto 🙂
