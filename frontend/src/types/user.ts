export type UserRole =
  | "super_admin"
  | "admin_cabinet"
  | "expert_comptable"
  | "chef_mission"
  | "collaborateur"
  | "assistant";

export interface UserAdmin {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  role: UserRole;
  is_active: boolean;
}

export interface UserCreatePayload {
  email: string;
  nom: string;
  prenom: string;
  password: string;
  role: UserRole;
}