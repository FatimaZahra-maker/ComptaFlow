import { useState } from "react";
import axios from "axios";
import { Eye, EyeOff, FileText, LockKeyhole, Mail, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/authApi";
import { requestAccessRenewal } from "../api/messagesApi";
import { useAuth } from "../context/AuthContext";
import "./LoginPage.css";

function LoginBrand() {
  return <div className="login-brand" aria-label="ComptaFlow">
    <svg className="login-brand-mark" viewBox="0 0 72 58" aria-hidden="true"><defs><linearGradient id="brand-orange" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f59b56" /><stop offset="1" stopColor="#d45b1f" /></linearGradient></defs><path d="M52 7H30C17 7 8 16 8 29s9 22 22 22h12V39H30c-6 0-10-4-10-10s4-10 10-10h16z" fill="url(#brand-orange)" /><path d="M31 25h30l-6 11H43v16H31z" fill="url(#brand-orange)" /></svg>
    <span>COMPTA<span>FLOW</span></span>
  </div>;
}

function DocumentIllustration() {
  return <div className="login-document-art" aria-hidden="true">
    <i className="scan-corner scan-top-left" /><i className="scan-corner scan-top-right" /><i className="scan-corner scan-bottom-left" /><i className="scan-corner scan-bottom-right" />
    <FileText /><div className="data-stream">{Array.from({ length: 28 }, (_, index) => <i key={index} />)}</div>
  </div>;
}

function AccountingIllustration() {
  const nodes = [[20,82],[42,45],[67,69],[84,24],[106,58],[126,28],[142,79],[158,46],[180,72],[195,36],[210,89],[111,106]];
  const links = [[0,1],[0,2],[1,2],[1,3],[2,4],[2,5],[3,5],[4,5],[4,6],[4,11],[5,7],[6,7],[6,8],[6,11],[7,9],[7,11],[8,9],[8,10],[9,10],[10,11]];
  return <div className="login-accounting-art" aria-hidden="true">
    <svg viewBox="0 0 230 130">{links.map(([from,to], index) => <line key={index} x1={nodes[from][0]} y1={nodes[from][1]} x2={nodes[to][0]} y2={nodes[to][1]} />)}{nodes.map(([x,y], index) => <circle key={index} cx={x} cy={y} r={index === 4 || index === 7 ? 7 : 5} className={index === 4 || index === 7 ? "active" : ""} />)}</svg>
    <div className="accounting-table"><div><span>▦ &nbsp;Compte</span><strong>6111</strong></div><div><span>♙ &nbsp;Fournisseur</span><strong>4011</strong></div><div><span>▤ &nbsp;Montant HT</span><strong>10 000,00</strong></div><div><span>% &nbsp;TVA</span><strong>2 000,00</strong></div><div><span>▦ &nbsp;TTC</span><strong>12 000,00</strong></div></div>
  </div>;
}

function loginErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Le serveur est inaccessible. Vérifiez que le backend est démarré.";
    const detail = error.response.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return "La connexion a échoué. Veuillez réessayer.";
}

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [showRecoveryHelp, setShowRecoveryHelp] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [recoveryStatus, setRecoveryStatus] = useState<string | null>(null);
  const [recoverySending, setRecoverySending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { setToken } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { access_token } = await login({ email: email.trim(), password });
      await setToken(access_token, rememberMe);
      navigate("/accueil", { replace: true });
    } catch (caught) {
      setError(loginErrorMessage(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRecoveryRequest() {
    if (!email.trim() || recoverySending) {
      setRecoveryStatus("Saisissez d’abord l’adresse e-mail de votre compte.");
      return;
    }
    setRecoverySending(true);
    setRecoveryStatus(null);
    try {
      setRecoveryStatus(await requestAccessRenewal(email.trim(), recoveryMessage.trim() || undefined));
      setRecoveryMessage("");
    } catch (caught) {
      setRecoveryStatus(loginErrorMessage(caught));
    } finally {
      setRecoverySending(false);
    }
  }

  return <main className="login-page">
    <div className="login-ledger login-ledger-left" aria-hidden="true" /><div className="login-ledger login-ledger-right" aria-hidden="true" />
    <DocumentIllustration /><AccountingIllustration />
    <section className="login-promise" aria-label="Promesse ComptaFlow"><h2>De la pièce à l’écriture,<br /><strong>en quelques secondes.</strong></h2><i /><p>Contrôle et pré-comptabilité<br />dans un seul espace sécurisé.</p></section>
    <section className="login-card" aria-labelledby="login-title">
      <LoginBrand />
      <div className="login-heading"><h1 id="login-title">Bienvenue sur ComptaFlow</h1><p>Connectez-vous à votre espace cabinet</p></div>
      <form onSubmit={handleSubmit} noValidate>
        {error && <div className="login-alert" role="alert">{error}</div>}
        <label htmlFor="login-email">Adresse e-mail</label>
        <div className="login-field"><Mail aria-hidden="true" /><input id="login-email" type="email" inputMode="email" autoComplete="email" placeholder="votre@email.com" value={email} onChange={(event) => setEmail(event.target.value)} required aria-invalid={Boolean(error)} /></div>
        <label htmlFor="login-password">Mot de passe</label>
        <div className="login-field"><LockKeyhole aria-hidden="true" /><input id="login-password" type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="••••••••••••" value={password} onChange={(event) => setPassword(event.target.value)} required aria-invalid={Boolean(error)} /><button type="button" className="password-toggle" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"} aria-pressed={showPassword}>{showPassword ? <EyeOff /> : <Eye />}</button></div>
        <div className="login-options"><label className="remember-option"><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} /><span aria-hidden="true" />Se souvenir de moi</label><button type="button" className="recovery-button" onClick={() => setShowRecoveryHelp((current) => !current)}>Mot de passe oublié&nbsp;?</button></div>
        {showRecoveryHelp && <div className="recovery-help"><p>Envoyez une demande sécurisée à l’administrateur de votre cabinet. Aucune adresse d’administrateur n’est exposée.</p><textarea aria-label="Message pour l’administrateur" rows={2} maxLength={500} value={recoveryMessage} onChange={(event) => setRecoveryMessage(event.target.value)} placeholder="Ex. Je n’arrive plus à accéder à mon compte." /><button type="button" disabled={recoverySending} onClick={() => void handleRecoveryRequest()}>{recoverySending ? "Envoi..." : "Envoyer la demande à l’administrateur"}</button>{recoveryStatus && <p className="recovery-status" role="status">{recoveryStatus}</p>}</div>}
        <button type="submit" disabled={isSubmitting || !email.trim() || !password} className="login-submit">{isSubmitting ? <><span className="login-spinner" /> Connexion...</> : "Se connecter"}</button>
      </form>
      <div className="login-security"><ShieldCheck aria-hidden="true" /> Accès sécurisé et données isolées par cabinet</div>
      <footer>ComptaFlow <span>•</span> v1.0</footer>
    </section>
  </main>;
}
