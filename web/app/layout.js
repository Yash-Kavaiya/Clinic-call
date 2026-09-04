import "./globals.css";

export const metadata = { title: "Clinic OS", description: "Reception console" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="app">{children}</div>
      </body>
    </html>
  );
}
