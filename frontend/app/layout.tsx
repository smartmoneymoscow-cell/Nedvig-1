import './globals.css';

export const metadata = {
  title: 'Realty Platform — AI Недвижимость',
  description: 'Агрегатор недвижимости с AI-агентом',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
