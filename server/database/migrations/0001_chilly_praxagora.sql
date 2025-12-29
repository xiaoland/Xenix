CREATE TABLE `projects` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project_id` text NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`dataset_ids` text,
	`work_item_ids` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `projects_project_id_unique` ON `projects` (`project_id`);--> statement-breakpoint
CREATE TABLE `work_items` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`work_item_id` text NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`project_id` text,
	`task_ids` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `work_items_work_item_id_unique` ON `work_items` (`work_item_id`);