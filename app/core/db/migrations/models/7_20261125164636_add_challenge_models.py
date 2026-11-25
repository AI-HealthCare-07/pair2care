from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `challenge_templates` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `title` VARCHAR(100) NOT NULL,
    `category` VARCHAR(30) NOT NULL COMMENT 'WALK: WALK\nWATER: WATER\nEXERCISE: EXERCISE\nSTRETCH: STRETCH\nLESS_ALCOHOL: LESS_ALCOHOL\nWEIGHT: WEIGHT\nNO_SMOKING: NO_SMOKING',
    `default_times_per_week` INT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `pairs` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `invite_code` VARCHAR(128) NOT NULL UNIQUE,
    `pair_key` VARCHAR(50) UNIQUE,
    `status` VARCHAR(8) NOT NULL COMMENT 'PENDING: PENDING\nACCEPTED: ACCEPTED\nENDED: ENDED' DEFAULT 'PENDING',
    `accepted_at` DATETIME(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `partner_id` BIGINT,
    `requester_id` BIGINT NOT NULL,
    CONSTRAINT `fk_pairs_users_a27c21a8` FOREIGN KEY (`partner_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_pairs_users_fe96ac01` FOREIGN KEY (`requester_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenges` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `title` VARCHAR(100) NOT NULL,
    `times_per_week` INT NOT NULL,
    `starts_on` DATE NOT NULL,
    `ends_on` DATE,
    `status` VARCHAR(9) NOT NULL COMMENT 'ACTIVE: ACTIVE\nCOMPLETED: COMPLETED\nENDED: ENDED' DEFAULT 'ACTIVE',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `challenge_template_id` BIGINT,
    `created_by_id` BIGINT NOT NULL,
    `pair_id` BIGINT,
    CONSTRAINT `fk_challeng_challeng_0a8461bf` FOREIGN KEY (`challenge_template_id`) REFERENCES `challenge_templates` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_challeng_users_8750cf56` FOREIGN KEY (`created_by_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_pairs_4042a834` FOREIGN KEY (`pair_id`) REFERENCES `pairs` (`id`) ON DELETE SET NULL
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenge_participants` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `status` VARCHAR(7) NOT NULL COMMENT 'INVITED: INVITED\nJOINED: JOINED\nLEFT: LEFT' DEFAULT 'INVITED',
    `times_per_week` INT,
    `joined_at` DATETIME(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `challenge_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    UNIQUE KEY `uid_challenge_p_challen_7aab77` (`challenge_id`, `user_id`),
    CONSTRAINT `fk_challeng_challeng_c273d8e6` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_users_190147ad` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenge_checks` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `checked_on` DATE NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `challenge_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    UNIQUE KEY `uid_challenge_c_challen_9fa29a` (`challenge_id`, `user_id`, `checked_on`),
    CONSTRAINT `fk_challeng_challeng_db15a945` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_users_f6df0e75` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `challenge_checks`;
        DROP TABLE IF EXISTS `challenge_participants`;
        DROP TABLE IF EXISTS `challenges`;
        DROP TABLE IF EXISTS `pairs`;
        DROP TABLE IF EXISTS `challenge_templates`;"""


MODELS_STATE = (
    "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"
)
