export interface Cabinet {
  id: string;
  nom: string;
  ice: string | null;
  adresse: string | null;
  telephone: string | null;
  email: string | null;
  is_active: boolean;
}

export interface CabinetUpdatePayload {
  nom?: string;
  ice?: string;
  adresse?: string;
  telephone?: string;
  email?: string;
}

export interface SystemInfo {
  ai_provider: string;
  groq_configure: boolean;
  ollama_model: string;
}
