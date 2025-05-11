import os
import base64
import PyPDF2
import spacy
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Carregar modelo de NLP
nlp = spacy.load("pt_core_news_sm")
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def authenticate_gmail():
    """Autentica e retorna um serviço da API do Gmail."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("C:/Users/Bernardo/Downloads/teste/credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def extract_text_from_pdf(pdf_path):
    """Extrai texto de um arquivo PDF."""
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

def extract_email(text):
    """Extrai um e-mail de um texto usando expressões regulares."""
    email_pattern = r"[a-zA-Z0-9._%+-]+@gmail.com"
    emails = re.findall(email_pattern, text)
    return emails[0] if emails else None

def extract_email_from_pdf(pdf_path):
    """Extrai o e-mail de um currículo em PDF."""
    text = extract_text_from_pdf(pdf_path)
    return extract_email(text)

def extract_name(text):
    """Extrai o nome do candidato com múltiplas estratégias e NLP para validação."""
    # Estratégia 1: Buscar padrões comuns como "Nome:"
    patterns = [r"Nome[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    # Estratégia 2: Assumir que as primeiras palavras são o nome do candidato
    words = text.split()
    if len(words) >= 2:
        potential_name = f"{words[0]} {words[1]}"
        
        # Estratégia 3: Usar NLP para validar se parece um nome
        doc = nlp(potential_name)
        if any(ent.label_ == "PER" for ent in doc.ents):  # "PER" = Pessoa
            return potential_name
    
    return "Candidato"

def extract_name_from_pdf(pdf_path):
    """Extrai o nome do candidato de um currículo em PDF."""
    text = extract_text_from_pdf(pdf_path)
    return extract_name(text)

def rank_candidates(job_description, resumes):
    """Rankeia currículos com base na similaridade de cosseno."""
    documents = [job_description] + resumes
    vectorizer = TfidfVectorizer().fit_transform(documents)
    similarity_matrix = cosine_similarity(vectorizer[0:1], vectorizer[1:])
    return similarity_matrix[0]

def send_email(candidate_email, candidate_name, rank, total_candidates):
    """Envia um e-mail usando a API do Gmail."""
    service = authenticate_gmail()
    greetings = "Parabéns" if rank == 1 else "Olá"
    intensity = "estamos muito interessados!" if rank == 1 else "gostaríamos de conversar." if rank <= total_candidates / 2 else "estamos avaliando possibilidades."
    
    # Link para o formulário
    form_link = "https://forms.gle/YcqpCo5qjVnnrkUn9"
    
    message_text = f"""
    {greetings} {candidate_name},
    
    Analisamos seu currículo e {intensity} Podemos agendar uma conversa?
    
    Para aumentar mais ainda suas chances de ser contratado, por gentileza responda o seguinte formulário: {form_link}
    
    Atenciosamente,
    Equipe de Recrutamento
    """
    
    message = MIMEText(message_text)
    message["to"] = candidate_email
    message["subject"] = "Oportunidade de Estágio"
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    message_body = {"raw": raw_message}
    
    try:
        service.users().messages().send(userId="me", body=message_body).execute()
        print(f"Email enviado para {candidate_name} ({candidate_email}) - Rank: {rank}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

def main(job_pdf, resumes_pdfs):
    job_description = extract_text_from_pdf(job_pdf)
    resumes = [extract_text_from_pdf(pdf) for pdf in resumes_pdfs]
    emails = [extract_email_from_pdf(pdf) for pdf in resumes_pdfs]
    names = [extract_name_from_pdf(pdf) for pdf in resumes_pdfs]
    candidates_info = list(zip(emails, names))
    scores = rank_candidates(job_description, resumes)
    ranked_candidates = sorted(zip(resumes_pdfs, scores, candidates_info), key=lambda x: x[1], reverse=True)
    
    for idx, (resume, score, (email, name)) in enumerate(ranked_candidates, 1):
        if email:
            send_email(email, name, idx, len(resumes_pdfs))
        else:
            print(f"Email não encontrado para {name} - Rank: {idx}")

# Exemplo de uso
job_pdf = "C:/Users/Bernardo/Downloads/vaga_estagio_ti.pdf"
candidates_pdfs = [
    "C:/Users/Bernardo/Downloads/curriculo 1.pdf",
    "C:/Users/Bernardo/Downloads/curriculo 2.pdf",
    "C:/Users/Bernardo/Downloads/curriculo 3.pdf",
    "C:/Users/Bernardo/Downloads/curriculo 4.pdf",
    "C:/Users/Bernardo/Downloads/curriculo 5.pdf"
]

main(job_pdf, candidates_pdfs)