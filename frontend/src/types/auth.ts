export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  role: string;
  cabinet_id: string;
}