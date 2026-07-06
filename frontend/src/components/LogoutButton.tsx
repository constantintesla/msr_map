import { useNavigate } from 'react-router-dom';
import { logout } from '../utils/auth';

export default function LogoutButton({ className = '' }: { className?: string }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className={`btn text-sm border border-zinc-600 px-3 py-1 min-h-0 ${className}`}
      onClick={() => logout(navigate)}
    >
      Выйти
    </button>
  );
}
