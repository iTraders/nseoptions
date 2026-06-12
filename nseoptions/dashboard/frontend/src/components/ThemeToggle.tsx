import { useEffect, useState } from "react";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Toggle the `dark` class on <html> (dark is the default). */
export function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setDark((value) => !value)}
      aria-label="Toggle colour theme"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
