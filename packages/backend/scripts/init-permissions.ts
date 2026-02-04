/**
 * Initialize default permissions and roles
 * Run this script after database migrations to set up the permission system
 */
import { AuthService } from "../src/services/AuthService";

async function main() {
  console.log("Initializing permissions...");

  const authService = new AuthService();

  try {
    await authService.initializePermissions();
    console.log("Permissions initialized successfully!");
    console.log("\nDefault roles:");
    console.log("- admin: Full access to all features");
    console.log(
      "- user: Limited access (cannot manage users or delete resources)",
    );
  } catch (error) {
    console.error("Failed to initialize permissions:", error);
    process.exit(1);
  }

  process.exit(0);
}

main();
