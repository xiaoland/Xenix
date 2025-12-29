-- Migration: Refactor schema to use integer IDs and foreign keys
DROP TABLE IF EXISTS `projects_new`;--> statement-breakpoint
CREATE TABLE `projects_new` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);--> statement-breakpoint
DROP TABLE IF EXISTS `projects`;--> statement-breakpoint
ALTER TABLE `projects_new` RENAME TO `projects`;--> statement-breakpoint
DROP TABLE IF EXISTS `work_items_new`;--> statement-breakpoint
CREATE TABLE `work_items_new` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project_id` integer NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);--> statement-breakpoint
DROP TABLE IF EXISTS `work_items`;--> statement-breakpoint
ALTER TABLE `work_items_new` RENAME TO `work_items`;--> statement-breakpoint
DROP TABLE IF EXISTS `datasets_new`;--> statement-breakpoint
CREATE TABLE `datasets_new` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project_id` integer,
	`name` text NOT NULL,
	`description` text,
	`file_path` text NOT NULL,
	`file_name` text NOT NULL,
	`file_size` integer,
	`columns` text,
	`row_count` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);--> statement-breakpoint
INSERT INTO `datasets_new` (id, name, description, file_path, file_name, file_size, columns, row_count, created_at, updated_at)
SELECT id, name, description, file_path, file_name, file_size, columns, row_count, created_at, updated_at
FROM `datasets`;--> statement-breakpoint
DROP TABLE `datasets`;--> statement-breakpoint
ALTER TABLE `datasets_new` RENAME TO `datasets`;--> statement-breakpoint
ALTER TABLE `tasks` ADD `work_item_id` integer;
