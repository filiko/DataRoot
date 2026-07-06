-- MySQL: backticks, AUTO_INCREMENT, inline ENUM, table-level FK
CREATE TABLE `authors` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(200) NOT NULL,
    `country` ENUM('us', 'uk', 'other') NOT NULL DEFAULT 'other',
    PRIMARY KEY (`id`)
);

CREATE TABLE `books` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `author_id` INT NOT NULL,
    `title` VARCHAR(500) NOT NULL,
    `published` DATETIME,
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_books_author` FOREIGN KEY (`author_id`)
        REFERENCES `authors` (`id`) ON DELETE CASCADE
);
