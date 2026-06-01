import { CommandChatbox } from "@/components/jarvis/CommandChatbox";

/** Jarvis command center — the conversational layer with four modes. */
export function JarvisPage() {
  return (
    <div className="h-full max-w-3xl mx-auto w-full">
      <CommandChatbox />
    </div>
  );
}
